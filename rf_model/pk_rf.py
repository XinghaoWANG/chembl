# Author: xiaotaw@qq.com (Any bug report is welcome)
# Time: Oct 2016
# Addr: Shenzhen
# Description: 

import math
import time
import numpy as np
from scipy import sparse

from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestClassifier

import pk_input as pki

# sensitivity, specificity, matthews correlation coefficient(mcc) 
def compute_performance(label, prediction):
  assert label.shape[0] == prediction.shape[0], "label number should be equal to prediction number"
  N = label.shape[0]
  APP = sum(prediction)
  ATP = sum(label)
  TP = sum(prediction * label)
  FP = APP - TP
  FN = ATP - TP
  TN = N - TP - FP - FN
  SEN = float(TP) / (ATP)
  SPE = float(TN) / (N - ATP)
  ACC = float(TP + TN) / N
  MCC = (TP * TN - FP * FN) / (math.sqrt((N - APP) * (N - ATP) * APP * ATP)) if not (N - APP) * (N - ATP) * APP * ATP == 0 else 0.0
  return TP, TN, FP, FN, SEN, SPE, ACC, MCC


if __name__ == "__main__":

  log_file = open("pk_rf.log", "w")
  log_file.write("target TP TN FP FN SEN SPE ACC MCC time\n")

  target_list = ["cdk2", "egfr_erbB1", "gsk3b", "hgfr", "map_k_p38a", "tpk_lck", "tpk_src", "vegfr2"]

  d = pki.Datasets(target_list, one_hot=False)

  for target in target_list:
    t0 = time.time()
    train_x = np.vstack([d.pos[target].features[d.pos[target].train_perm], d.neg.features[d.neg.train_perm]])
    train_y = np.hstack([d.pos[target].labels[d.pos[target].train_perm], d.neg.mask_dict[target][d.neg.train_perm]])
    test_perm = d.pos[target].test_perm
    test_x = np.vstack([d.pos[target].features[d.pos[target].test_perm], d.neg.features[d.neg.test_perm]])
    test_y = np.hstack([d.pos[target].labels[d.pos[target].test_perm], d.neg.mask_dict[target][d.neg.test_perm]])
    clf = RandomForestClassifier(n_estimators=100, max_features=1.0/3, n_jobs=8, max_depth=None, min_samples_split=5, random_state=0)
    clf.fit(train_x, train_y)
    train_pred = clf.predict(train_x)
    result = compute_performance(train_y, train_pred)
    t1 = time.time()
    print("train: %s %s %5f" % (target, result, t1-t0))
    log_file.write("train: %s %s %5f\n" % (target, result, t1-t0))
    test_pred = clf.predict(test_x)
    result = compute_performance(test_y, test_pred)
    t2 = time.time()
    print("test: %s %s %5f" % (target, result, t2-t0))
    log_file.write("test: %s %s %5f\n" % (target, result, t2-t0))

  log_file.close()

