# Author: xiaotaw@qq.com (Any bug report is welcome)
# Time Created: Nov 2016
# Time Last Updated: Dec 2016
# Addr: Shenzhen, China
# Description:

import os
import getpass
import numpy as np
import pandas as pd
from scipy import sparse
from collections import defaultdict

data_dir = "/home/%s/Documents/chembl/data_files/" % getpass.getuser()
fp_dir = os.path.join(data_dir, "fp_files")
mask_dir = os.path.join(data_dir, "mask_files")
structure_dir = os.path.join(data_dir, "structure_files")

def dense_to_one_hot(labels_dense, num_classes=2, dtype=np.int):
  """Convert class labels from scalars to one-hot vectors.
  Args:
    labels_dense: <type 'numpy.ndarray'> dense label
    num_classes: <type 'int'> the number of classes in one hot label
    dtype: <type 'type'> data type
  Return:
    labels_ont_hot: <type 'numpy.ndarray'> one hot label
  """
  num_labels = labels_dense.shape[0]
  index_offset = np.arange(num_labels) * num_classes
  labels_one_hot = np.zeros((num_labels, num_classes))
  labels_one_hot.flat[index_offset + labels_dense.ravel().astype(dtype)] = 1
  return labels_one_hot

def sparse_features(fps_list, columns_dict, target_apfp_picked, is_log=True):
  data = []
  indices = []
  indptr = [0]
  for fps_str in fps_list:
    n = indptr[-1]
    for fp in fps_str[1:-1].split(","):
      if ":" in fp:
        k, v = fp.split(":")
        indices.append(columns_dict[int(k)])
        data.append(int(v))
        n += 1
    indptr.append(n)
  data = np.array(data)
  if is_log:
    data = np.log(data)
  a = sparse.csr_matrix((data, indices, indptr), shape=(len(fps_list), len(target_apfp_picked) + 1))
  return a

# the newly picked out 15 targets, include 9 targets from 5 big group, and 6 targets from others.
target_list = ["CHEMBL279", "CHEMBL203", # Protein Kinases
               "CHEMBL217", "CHEMBL253", # GPCRs (Family A)
               "CHEMBL235", "CHEMBL206", # Nuclear Hormone Receptors
               "CHEMBL240", "CHEMBL4296", # Voltage Gated Ion Channels
               "CHEMBL4805", # Ligand Gated Ion Channels
               "CHEMBL204", "CHEMBL244", "CHEMBL4822", "CHEMBL340", "CHEMBL205", "CHEMBL4005" # Others
              ] 

class Dataset(object):
  """Base dataset class 
  """
  def __init__(self, target=target_list[0], one_hot=True, is_shuffle_train=True):
    """Constructor, create a dataset container. 
    Args:
      size: <type 'int'> the number of samples
      is_shuffle: <type 'bool'> whether shuffle samples when the dataset created
      fold: <type 'int'> how many folds to split samples
    Return:
      None
    """
    # read top 79 targets' label
    self.clf_label_79 = pd.read_csv(structure_dir + "/chembl_top79.label", usecols=[0, 2, 3, 4], delimiter="\t")
    # read target's label
    self.target_clf_label = self.clf_label_79[self.clf_label_79["TARGET_CHEMBLID"] == target]
    # read chembl id and apfp
    self.chembl_id = []
    self.chembl_apfp = {}
    f = open(fp_dir + "/chembl.apfp", "r")
    for line in f:
      id_, fps_str = line.split("\t")
      id_ = id_.strip()
      fps_str = fps_str.strip()
      self.chembl_id.append(id_)
      self.chembl_apfp[id_] = fps_str
    f.close()
    # read pns apfp
    self.pns_id = []
    self.pns_apfp = {}
    f = open(fp_dir + "/pubchem_neg_sample.apfp", "r")
    for line in f:
      id_, fps_str = line.split("\t")
      id_ = id_.strip()
      fps_str = fps_str.strip()
      self.pns_id.append(id_)
      self.pns_apfp[id_] = fps_str                
    f.close()
    # read mask
    self.target_pns_mask = pd.Series.from_csv(mask_dir + "/%s_pns.mask" % target, header=None, sep="\t")
    self.target_cns_mask = pd.Series.from_csv(mask_dir + "/%s_cns.mask" % target, header=None, sep="\t")
    # read count and the apfps that were picked out 
    counts = np.genfromtxt(mask_dir + "/%s_apfp.count" % target, delimiter="\t", dtype=int)
    self.target_apfp_picked = counts[counts[:, 1] > 10][:, 0]
    self.target_apfp_picked.sort()
    # columns and sparse features
    self.target_columns_dict = defaultdict(lambda : len(self.target_apfp_picked))
    for i, apfp in enumerate(self.target_apfp_picked):
      self.target_columns_dict[apfp] = i
    # generate features
    self.target_pns_features = sparse_features([self.pns_apfp[k] for k in self.pns_id], self.target_columns_dict, self.target_apfp_picked)[:, :-1]
    self.target_cns_features = sparse_features([self.chembl_apfp[k] for k in self.chembl_id], self.target_columns_dict, self.target_apfp_picked)[:, :-1]
    # time split
    time_split_test = self.target_clf_label[self.target_clf_label["YEAR"] > 2014]
    m = self.target_cns_mask.index.isin(time_split_test["CMPD_CHEMBLID"])
    self.target_cns_features_test = self.target_cns_features[m]
    self.target_cns_features_train = self.target_cns_features[~m]
    self.target_cns_mask_test = self.target_cns_mask[m]
    self.target_cns_mask_train = self.target_cns_mask[~m]
    # train 
    self.train_features = sparse.vstack([self.target_cns_features_train, self.target_pns_features])
    self.train_labels = np.hstack([self.target_cns_mask_train, self.target_pns_mask]).astype(int)
    # test
    self.test_features = self.target_cns_features_test
    self.test_labels = self.target_cns_mask_test.values.astype(int)
    # one_hot
    if one_hot:
      self.train_labels_one_hot = dense_to_one_hot(self.train_labels) 
      self.test_labels_one_hot = dense_to_one_hot(self.test_labels) 
    # batch related
    self.train_size = self.train_features.shape[0] # (954049, 9412)
    self.train_perm = np.array(range(self.train_size))
    if is_shuffle_train:
      np.random.shuffle(self.train_perm)
    self.train_begin = 0
    self.train_end = 0

    self.cns_size = self.target_cns_features.shape[0] # (878721, 9412)
    self.cns_perm = np.arange(self.cns_size)
    self.cns_begin = 0
    self.cns_end = 0

  def generate_perm_for_train_batch(self, batch_size):
    """Create the permutation for a batch of train samples
    Args:
      batch_size: <type 'int'> the number of samples in the batch
    Return:
      perm: <type 'numpy.ndarray'> the permutation of samples which form a batch
    """
    self.train_begin = self.train_end
    self.train_end += batch_size
    if self.train_end > self.train_size:
      np.random.shuffle(self.train_perm)
      self.train_begin = 0
      self.train_end = batch_size
    perm = self.train_perm[self.train_begin: self.train_end]
    return perm

  def generate_train_batch(self, batch_size):
    perm = self.generate_perm_for_train_batch(batch_size)
    return self.train_features[perm].toarray().astype(np.float32), self.train_labels_one_hot[perm]

  def reset_begin_end(self):
    self.train_begin = 0
    self.train_end = 0

  def generate_train_batch_once(self, batch_size):
    self.train_begin = self.train_end
    self.train_end += batch_size
    if self.train_end > self.train_size:
      self.train_end = self.train_size
    perm = self.train_perm[self.train_begin: self.train_end]
    return self.train_features[perm].toarray().astype(np.float32), self.train_labels_one_hot[perm]

  def reset_begin_end_cns(self):
    self.cns_begin = 0
    self.cns_end = 0

  def generate_cns_batch_once(self, batch_size):
    self.cns_begin = self.cns_end
    self.cns_end += batch_size
    if self.cns_end > self.cns_size:
      self.cns_end = self.cns_size
    perm = self.cns_perm[self.cns_begin: self.cns_end]
    return self.target_cns_features[perm].toarray().astype(np.float32), dense_to_one_hot(self.target_cns_mask[perm].astype(int))


# dataset for virtual screening(vs)
class DatasetVS(object):
  def __init__(self, target=target_list[0]):
    # read count and the apfps that were picked out 
    counts = np.genfromtxt(mask_dir + "/%s_apfp.count" % target, delimiter="\t", dtype=int)
    self.target_apfp_picked = counts[counts[:, 1] > 10][:, 0]
    self.target_apfp_picked.sort()
    # columns and sparse features
    self.target_columns_dict = defaultdict(lambda : len(self.target_apfp_picked))
    for i, apfp in enumerate(self.target_apfp_picked):
      self.target_columns_dict[apfp] = i

  def reset(self, fp_fn):
    # read chembl id and apfp
    self.pubchem_id = []
    self.pubchem_apfp = {}
    f = open(fp_fn, "r")
    for line in f:
      id_, fps_str = line.split("\t")
      id_ = id_.strip()
      fps_str = fps_str.strip()
      self.pubchem_id.append(id_)
      self.pubchem_apfp[id_] = fps_str
    f.close()
    # generate features
    self.features = sparse_features([self.pubchem_apfp[k] for k in self.pubchem_id], self.target_columns_dict, self.target_apfp_picked)[:, :-1]


def compute_performance(label, prediction):
  """sensitivity(SEN), specificity(SPE), accuracy(ACC), matthews correlation coefficient(MCC) 
  """
  assert label.shape[0] == prediction.shape[0], "label number should be equal to prediction number"
  N = label.shape[0]
  APP = sum(prediction)
  ATP = sum(label)
  TP = sum(prediction * label)
  FP = APP - TP
  FN = ATP - TP
  TN = N - TP - FP - FN
  SEN = float(TP) / (ATP) if ATP != 0 else np.nan
  SPE = float(TN) / (N - ATP)
  ACC = float(TP + TN) / N
  MCC = (TP * TN - FP * FN) / (np.sqrt(long(N - APP) * long(N - ATP) * APP * ATP)) if not (N - APP) * (N - ATP) * APP * ATP == 0 else 0.0
  return TP, TN, FP, FN, SEN, SPE, ACC, MCC



#train_result = compute_performance(train_labels, train_pred)
#test_result = compute_performance(target_cns_mask_test.values.astype(int), test_pred)






