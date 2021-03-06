import numpy as np
import common.time as time
from collections import namedtuple
from graphsage.Graph_Learning_utils import Hybrid_Rep_Feat, plot_samples
from sklearn import  preprocessing
import os
from MIT_dataset_utils import load_edf_data
from numpy import fft
from scipy.signal import hilbert
from scipy.fftpack import rfft, irfft, fftfreq
from scipy.signal import butter, lfilter
import matplotlib.pyplot as plt
import gc
#import matlab.engine
# import more_itertools
import sys
import tensorflow as tf
from utils import load_EU_features, load_side_adj, load_EU_settings, sec2win, win2sec, inpython_online_wrapper
import random
from tensorflow.contrib.tensor_forest.python import tensor_forest
from tensorflow.python.ops import resources
from utils import NN_classifier, RandomForest_classifier, class_relabel, rolling_window
from sklearn.ensemble import RandomForestClassifier
from graphsage.Graph_Learning_utils import fine_eval_performance, coarse_eval_performance
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit
import matlab.engine
import itertools
#from main_checkpoint import load_Core
class NN_properties (object):
    def __init__(self, n_hidden_1, n_hidden_2, n_hidden_3, n_hidden_4, loss_type):
        self.n_hidden_1 = n_hidden_1
        self.n_hidden_2 = n_hidden_2
        self.n_hidden_3 = n_hidden_3
        self.n_hidden_4 = n_hidden_4
        self.loss_type = loss_type
        
class RF_properties (object):
    def __init__(self, loss_type, num_trees, num_classes, num_features):
        with tf.variable_scope(tf.get_variable_scope(), reuse=tf.AUTO_REUSE):
            hparams = tensor_forest.ForestHParams(num_classes=num_classes, 
                                                  num_features=num_features, 
                                                  num_trees=num_trees).fill() # max_nodes=max_nodes
            # Build the Random Forest
            self.forest_graph =  tensor_forest.RandomForestGraphs(hparams)       
    #         tensor_forest.TrainingLossForest(hparams, loss_fn=_loss_fn)

       
        self.loss_type = loss_type
        self.num_trees = num_trees


GraphLCore = namedtuple('GraphLCore', ['model_size', 'num_nodes', 'dim', 'fixed_params','aggregator_type',\
                                       'concat','num_layers', 'coordinate_gradient', 'projected_gradient',\
                                       'conv_sizes', 'side_adj_mat', 'A_val_string', 'dimArray'])

# class GraphLCore (object):
#     def __init__(self, model_size, num_nodes, dim, fixed_params, aggregator_type,\
#                                        concat, num_layers, coordinate_gradient, projected_gradient,\
#                                             conv_sizes, side_adj_mat, A_val_string, dimArray):

class ClassifCore (object):
    
    def __init__(self, epochs, learning_rate, num_classes,max_total_steps,batch_size, \
                        classifier, classifier_properties, num_features,\
                            sensitivity_score_target,eval_thresh_func, mvAvg_winlen):
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.num_classes = num_classes
        self.max_total_steps = max_total_steps
        self.batch_size = batch_size
        self.classifier = classifier
        self.classifier_properties = classifier_properties
        self.num_features = num_features
        self.sensitivity_score_target = sensitivity_score_target
        self.eval_thresh_func = eval_thresh_func
        self.mvAvg_winlen = mvAvg_winlen
# LoadCore = namedtuple('ClassifCore', ['howmany_to_load', 'num_windows', 'sampling_freq', 'data_conversions',\
#                                        'num_classes', 'train_test', 'start_num', 'concat', 'down_sampl_ratio',
#                                        'freq_bands', 'initial_freq_band', 'only_seizures', 'welchs_win_len',
#                                        'welchs_stride', 'state_win_lengths', 'detection_flag',
#                                        'dataSet', 'matlab_engin'])


class Task(object):
    
    def __init__(self, task_core):
        self.task_core = task_core


def X_to_W(arr):
    arr = arr.reshape(arr.shape[0], -1)
    W = np.abs(np.matmul(arr, np.swapaxes(arr, 1, 2)))
    return np.reshape(W, (W.shape[0], -1))  # np.array([W[i,np.triu_indices(W.shape[-1])] for i in np.arange(W.shape[0])])

def X_flat_complex(arr):
    arr_flat = arr.reshape(arr.shape[0], -1)
    return np.concatenate((np.real(arr_flat), np.imag(arr_flat)), axis=1)
     
    
    
class train_test(Task):

    def run(self):
        flags = tf.app.flags
        FLAGS = flags.FLAGS
        remaining_args = FLAGS([sys.argv[0]] + [flag for flag in sys.argv if flag.startswith("--")])
        assert(remaining_args == [sys.argv[0]])
        num_nodes, dimArray, matlab_load_core = data_load(self.task_core).run(None) # matlab_load_core.side_adj_mean
        
        num_classes = np.unique(matlab_load_core.y_train).size # 1 + (1 if detection_flag else 0) + len(state_win_lengths)
        num_features = int(num_nodes*(num_nodes+1)/2)
        X_train = matlab_load_core.X_train
        y_train = matlab_load_core.y_train
        if('fine' in self.task_core.TrainTest_mode):
            X_test = matlab_load_core.X_test
            y_test = matlab_load_core.y_test
        else:
            X_test = None 
            y_test = None 
        # Training and Validation
        sensitivity_score_target = [1, 0.92, 0.85]
        valid_split_ratio = 5
        weight_losses = 1
        
        
        # Hyperparameters
        epochs_arr = [1]
        learning_rate_arr = [0.1] #, 0.001]
        num_trees_arr = [1000] #, 100, 5000]
        eval_thresh_func_arr = [np.mean]
        batch_size_arr = [200]
        aggregator_type_arr = ['mean'] # 'mean', 'maxpool'
        side_adj_mat_arr = [ None ] # (2*matlab_load_core.structural_inf.adj_means[0]-1)] # 
        A_val_string_arr = ['optimizedA' if side_adj_mat is None else 'fixedA_invCov' for side_adj_mat in side_adj_mat_arr]
        mvAvg_winlen = 3 # sec2win(2)
        # 253: 3 1125: 5
        # definition of W from Z
        # # of bands to use
        
        hyperparams_arr = list(itertools.product(epochs_arr, learning_rate_arr,\
                                                  num_trees_arr, eval_thresh_func_arr,\
                                                   batch_size_arr, aggregator_type_arr,\
                                                   A_val_string_arr))
        
        valSplitter = StratifiedKFold(n_splits=valid_split_ratio)
        all_valid_measures = []
        hypparamCounter = 0
        for epochs, learning_rate, num_trees, eval_thresh_func, batch_size, aggregator_type, A_val_string in hyperparams_arr:
            side_adj_mat = side_adj_mat_arr[hypparamCounter]
            in_valid_measures = []
            in_train_measures = []
            for train_idx, valid_idx in valSplitter.split(np.arange(y_train.size), y_train):
#                 train_idx = valid_idx = np.arange(y_train.size)
#                 train_idx, valid_idx = valSplitter.split(np.arange(y_train.size), y_train)[0]
                if(self.task_core.feature_mode == 'W_graphL'):
                    if(True):
                        classifier = RandomForest_classifier 
                        classifier_properties = RF_properties(loss_type='softmax', num_trees=num_trees, num_classes=num_classes, num_features=num_features)
                    else:
                        classifier = NN_classifier 
                        classifier_properties = NN_properties(n_hidden_1=256, n_hidden_2=None, \
                                                              n_hidden_3=None, n_hidden_4=None, loss_type='softmax')
                        
                    graphL_core = GraphLCore(model_size='small', num_nodes=num_nodes, dim=np.prod(dimArray), fixed_params=False, aggregator_type=aggregator_type,\
                                        concat=False, num_layers=2, coordinate_gradient=False, projected_gradient=True, \
                                        conv_sizes=matlab_load_core.conv_sizes, side_adj_mat=side_adj_mat, A_val_string = A_val_string, \
                                        dimArray=dimArray) 
                    
                    classification_core = ClassifCore(classifier=classifier, classifier_properties=classifier_properties,
                                              epochs=epochs, learning_rate=learning_rate,\
                                              num_classes=num_classes, max_total_steps=1e10, \
                                              batch_size=batch_size, num_features=num_features,\
                                              sensitivity_score_target=sensitivity_score_target,\
                                              eval_thresh_func=eval_thresh_func, mvAvg_winlen=mvAvg_winlen)
                    
                    feature_extraction = Hybrid_Rep_Feat(graphL_core, classification_core, matlab_load_core, weight_losses)
#                     feature_extraction.test(X_test, y_test, self.task_core.target, train_test='testing', \
#                                                     out_th = np.arange(0.27, 0.32, 0.008), printing_flag=True) 
                    feature_extraction.train(X_train[train_idx,...], y_train[train_idx], self.task_core.target, printing_flag=False)
                    feature_extraction.printing(self.task_core.adj_calc_mode)
                    _, prob_hat_train, _ = feature_extraction.test(X_train[train_idx,...], y_train[train_idx], \
                                                                                       self.task_core.target, train_test='training', printing_flag=False)
                    _, prob_hat_valid, _ = feature_extraction.test(X_train[valid_idx,...], y_train[valid_idx], \
                                                                                       self.task_core.target, train_test='validation', printing_flag=False) 
                else:
                    clf = RandomForestClassifier(n_estimators=num_trees)
                if(self.task_core.feature_mode == 'W_raw'): 
                    clf = clf.fit( X_to_W(X_train[train_idx,...]), y_train[train_idx])
                    prob_hat_train = clf.predict_proba(X_to_W(X_train[train_idx,...]))[:, 1]
                    prob_hat_valid = clf.predict_proba(X_to_W(X_train[valid_idx,...]))[:, 1]
                elif(self.task_core.feature_mode == 'X_raw'): 
                    clf = clf.fit(np.reshape(X_train[train_idx,...], (train_idx.size,-1)), y_train[train_idx])
                    prob_hat_train = clf.predict_proba(np.reshape(X_train[train_idx,...], (train_idx.size,-1)))[:, 1]
                    prob_hat_valid = clf.predict_proba(np.reshape(X_train[valid_idx,...], (valid_idx.size,-1)))[:, 1]
                print('TRAINING')
                in_train_measures.append(fine_eval_performance(y_train[train_idx], prob_hat_train, sensitivity_score_target, printing_flag=True))
                in_valid_measures.append(fine_eval_performance(y_train[valid_idx], prob_hat_valid, sensitivity_score_target, printing_flag=False))
                break
            
            valid_measures = [eval_thresh_func(np.vstack([measure[i] for measure in in_valid_measures]), axis=0) for i in range(len(in_valid_measures[0]))]
            all_valid_measures.append(valid_measures)
            print(' Validation hyperparms are: epochs = %d, learning_rate = %f, num_trees = %d, eval_thresh_func = %s, batch_size = %d, aggregator-type=%s, A_val_string=%s' %\
                   (epochs, learning_rate, num_trees, eval_thresh_func, batch_size, aggregator_type, A_val_string))
            print ('    FA number=%s from %d samples and  %d zero samples, for sensitivity=%s, threshold=%s, AUC=%f' 
                        % (valid_measures[1], valid_idx.size, np.argwhere(y_train[valid_idx]==0).size, \
                             valid_measures[3], valid_measures[2], valid_measures[0]))
            print('-------')
                
            
        valid_eval_threshold = np.sort(np.unique(np.hstack((np.arange(0.27, 0.5, 0.003), np.arange(0.284, 0.296, 0.0008))))) # np.arange(0.25, 0.5, 0.005) # # choose_hyperparams(valid_measures, eval_thresh_func) # None 
        # 253: mvAvg_winlen = 3, np.arange(0.33, 0.35, 0.002) 
        # 1125:  mvAvg_winlen = 3, np.arange(0.28, 0.32, 0.004)
        # 264: mvAvg_winlen = 3, np.arange(0.35, 0.36, 0.001)
#             rank_hyperparams(itertools.product(epochs_arr, learning_rate_arr, num_trees_arr, eval_thresh_func_arr, batch_size_arr), valid_measures)
        best_hyper = np.argmax(np.vstack([measure[0] for measure in all_valid_measures]))
        print('*** VALIDATION for patient ' + str(self.task_core.target))
        print('    Best hyperparms are: epochs = %d, learning_rate = %f, num_trees = %d, eval_thresh_func = %s, batch_size = %d, aggregator-type=%s, A_val_string=%s'\
               % (hyperparams_arr[best_hyper]))
        print ('        FA number=%s from %d samples and  %d zero samples, for sensitivity=%s, threshold=%s, AUC=%f' 
                        % (  all_valid_measures[best_hyper][1], valid_idx.size, np.argwhere(y_train[valid_idx]==0).size, \
                             all_valid_measures[best_hyper][3], all_valid_measures[best_hyper][2], all_valid_measures[best_hyper][0]))
        print('------------------------------------------------------')
        print('------------------------------------------------------')
        hypparamCounter += 1
        # Testing
        if(self.task_core.feature_mode == 'W_graphL'):
             
            y_hat_test, prob_hat_test, W_hat_test = feature_extraction.test(X_test, y_test, self.task_core.target, train_test='testing', \
                                                                                out_th=valid_eval_threshold, printing_flag=True) 
#             plot_samples(y_hat_test, y_test, prob_hat_test, W_hat_test, matlab_load_core,\
#                             self.task_core, matlab_load_core.clip_sizes_test, \
#                                 matlab_load_core.sel_win_nums_test, 'RepL', num_plots=10*15)
             
        elif(self.task_core.feature_mode == 'W_raw'):            
#             clf = clf.fit(X_flat_complex(matlab_load_core.X_train), matlab_load_core.y_train)
#             prob_hat = clf.predict_proba(X_flat_complex(matlab_load_core.X_test))[:, 1]
#             print('***** FINAL TESTING initial features for patient '+ str(self.task_core.target))
#             eval_performance(matlab_load_core.y_test, None, prob_hat, "testing")  
#             print('********')
            if(X_test is not None):
                if(self.task_core.feature_mode == 'W_raw'): 
                    prob_hat = clf.predict_proba(X_to_W(X_test))[:, 1]
                elif(self.task_core.feature_mode == 'X_raw'): 
                    prob_hat = clf.predict_proba(np.reshape(X_test, (X_test.shape[0], -1)))[:, 1]
                print('***** FINAL TESTING W of initial features for patient '+ str(self.task_core.target))
                fine_eval_performance(y_test, prob_hat, sensitivity_score_target, th=valid_eval_threshold, matlab_load_core=matlab_load_core)  
                print('********')
            else:
                classif_loadbatch = online_load(matlab_load_core)
                total_steps = 0
                prob_hat = None
                y_true = None
                while(not classif_loadbatch.end()):
                    classif_loadbatch.next()
                    inn_prob = clf.predict_proba(X_to_W(classif_loadbatch.current_x()))[:, 1]
                    prob_hat = inn_prob if prob_hat is None else np.concatenate((prob_hat, inn_prob), axis=0)
                    y_true = classif_loadbatch.current_y() if y_true is None else np.concatenate((y_true, classif_loadbatch.current_y()), axis=0)
                    print('--- %f percent of testing is done, %d samples so far' % (total_steps*100/matlab_load_core.settings_TestNumFiles, y_true.size) )
                    coarse_eval_performance(y_true, prob_hat, sensitivity_score_target, th=valid_eval_threshold, matlab_load_core=matlab_load_core,
                                            mvAvg_winlen=classification_core.mvAvg_winlen) 
                    total_steps += 1 
        return 

def rank_hyperparams(hyperparams, measures):
    AUCs = np.vstack([measure[0] for measure in measures])
    data = zip(AUCs, hyperparams)
    for AUC, hyperparam in data.sort(key=lambda pair: float(pair[0])):
        print('AUC=%f , hyperparams = %s' %(float(AUC), hyperparam))
    return 
    
    
def choose_hyperparams(valid_measures, eval_thresh_func):
    eval_threshold = eval_thresh_func(np.vstack([measure[2] for measure in valid_measures]), axis=0)
    return eval_threshold



class online_load():
    def __init__(self, matlab_load_core):
        self.batch_num = matlab_load_core.settings_TrainNumFiles
        self.matlab_load_core = matlab_load_core # matlab_load_core.settings_numFiles
        self.matlab_engin = matlab.engine.start_matlab()
    def current_x(self):
        return self.dataX
    def current_y(self):
        return self.dataY
    def next(self):
        self.batch_num += 1
        self.dataX, self.dataY, sel_win_nums, conv_sizes, clip_sizes = \
                    inpython_online_wrapper(self.matlab_engin, self.matlab_load_core, [self.batch_num], 'total')
        
        return 
    def end(self):
        return self.batch_num > self.matlab_load_core.settings_TrainNumFiles + self.matlab_load_core.settings_TestNumFiles



def train_test_splitting(y, split_ratio, clip_sizes=None):
    random.seed(0)
    def rand_sel(arr, indx, split_ratio): # from array, choose half of 1's and half of 0's randomly
        szr_indx = np.squeeze(np.argwhere(arr!=0))
        szr_samples = random.sample(list(indx[szr_indx]), int(split_ratio*szr_indx.size))
        nonszr_indx = np.squeeze(np.argwhere(arr==0))
        nonszr_samples = random.sample(list(indx[nonszr_indx]), int(split_ratio*nonszr_indx.size))
        return np.concatenate((szr_samples,nonszr_samples))
        
    if(clip_sizes is None): # later: shuffle and stuff
        return rand_sel(y, np.arange(y.size), split_ratio)
    else: # later
        # from each clip, choose half of 1's and half of 0's randomly
        train_idx = np.concatenate([rand_sel(y[np.arange(clip_sizes[i,0],clip_sizes[i,1])], np.arange(clip_sizes[i,0],clip_sizes[i,1]), split_ratio) 
                                                    for i in range(clip_sizes.shape[0])])
        test_idx = np.array(list(set(np.arange(y.size))-set(train_idx)))
        return train_idx, test_idx
    
    
def h5py2complex(f, keyy):
    try:
        temp = f[keyy].value
    except:
        temp = f[keyy]
        print('f[key]: ', temp.shape)
        print(temp.view(np.double).shape)
    arr = temp.view(np.double).reshape(np.concatenate((temp.shape , [2])))
    return np.nan_to_num(arr[...,0] + 1j*arr[...,1])


class Matlab_Load_Core():
    
    def __init__(self, matFile):
        conv_sizes = np.array(matFile['conv_sizes'])
        self.conv_sizes = np.reshape(conv_sizes, (conv_sizes.size,))
        
        soz_ch_ids = np.array(matFile['soz_ch_ids'])
        self.soz_ch_ids = np.reshape(soz_ch_ids, (soz_ch_ids.size,))
        
        self.pre_ictal_num_win = int(np.array(matFile['n_pre_szr']))
        
        self.window_size_sec = 2.5 #np.float32(np.array(matFile['window_size_sec']))
        self.stride_sec = 1.5 # np.float32(np.array(matFile['stride_sec']))
        
        self.X_train = h5py2complex(matFile, 'X_train')
        
        y = np.nan_to_num(np.array(matFile['y_train']))
        self.y_train = np.reshape(y, (y.size,))
        
        
        sel_win_nums = np.array(matFile['sel_win_nums_train'])
        self.sel_win_nums_train = np.reshape(sel_win_nums, (sel_win_nums.size,))
        self.clip_sizes_train = np.array(matFile['clip_sizes_train'])
        
        self.X_test = np.nan_to_num(np.array(matFile['X_test']))
        y = np.nan_to_num(np.array(matFile['y_test']))
        self.y_test = np.reshape(y, (y.size,))
        
        
        sel_win_nums = np.array(matFile['sel_win_nums_test'])
        self.sel_win_nums_test = np.reshape(sel_win_nums, (sel_win_nums.size,))
        self.clip_sizes_test = np.array(matFile['clip_sizes_test'])
        
        if(y.size != self.X_train.shape[0]):
            self.X_train = np.swapaxes(np.swapaxes(self.X_train, 0, 3), 1, 2)
            try:
                self.X_test = np.swapaxes(np.swapaxes(self.X_test, 0, 3), 1, 2)
            except:
                pass
            

class data_load(Task):
    
    
    def EU_matlab_run(self, load_Core):
        start_time = time.get_seconds()
        
#         load_Core.matlab_engin.loading_EU_main(nargout=0)
#         X = load_Core.matlab_engin.workspace['X']
#         y = load_Core.matlab_engin.workspace['y']
        
        matFile = load_EU_features(self.task_core.data_dir , self.task_core.target, load_Core)
        
        matlab_load_core = Matlab_Load_Core(matFile)
        matlab_load_core.target = self.task_core.target
        matlab_load_core.y_train = class_relabel(matlab_load_core.y_train)
        if(matlab_load_core.y_test is not None):
            matlab_load_core.y_test = class_relabel(matlab_load_core.y_test)
            
        matlab_load_core.structural_inf = load_side_adj(self.task_core.sidinfo_dir, self.task_core.target, self.task_core.adj_calc_mode, load_Core)
        
        print('    X training', matlab_load_core.X_train.shape, 'y training', matlab_load_core.y_train.shape)
        print('    X testing', matlab_load_core.X_test.shape, 'y testing', matlab_load_core.y_test.shape)
        
        matlab_load_core.settings_TrainNumFiles, matlab_load_core.settings_TestNumFiles = load_EU_settings(self.task_core.settings_dir , self.task_core.target, load_Core)
        
        print('    time elapsed: ', time.get_seconds()-start_time)
        return  matlab_load_core.X_train.shape[1],  matlab_load_core.X_train.shape[2:], matlab_load_core
    
    
    def MITCHB_run(self, load_Core):
        start_time = time.get_seconds()
        out_data = load_edf_data(self.task_core.data_dir , self.task_core.target, load_Core)
        num_clips = []
        if(load_Core.concat):
            X = None
            y = None
        else:
            X = []
            y = []
        
        for data, file_name, seizure_start_time_offsets, seizure_lengths in out_data:
            inner_x, inner_y, num_nodes, dim, conv_sizes = windowing_data(data, seizure_start_time_offsets, seizure_lengths, load_Core)
#             print('inner_x: ', np.array(inner_x).shape)
#             num_clips.append(np.array(inner_x).shape[0])
            if(load_Core.concat):
                if(X is None):
                    X = np.array(inner_x)
                    y = np.array(inner_y)
                else:
                    X = np.concatenate((X,inner_x), axis=0)
                    y = np.concatenate((y,inner_y), axis=0)
            else:
                X.append(inner_x)
                y.append(inner_y)
    
        X = np.array(X)
        y = np.array(y)
        print('    X', X.shape, 'y', y.shape)
        print('    time elapsed: ', time.get_seconds()-start_time)
        return X, y, num_nodes, dim, conv_sizes  #, num_clips
    
    
    def run(self, load_Core):
        print ('Loading data') 
        return self.EU_matlab_run(load_Core)
#         if(load_Core.dataSet =='EU'):
#             return self.EU_matlab_run(load_Core)
#         else:
#             return self.MITCHB_run(load_Core)
        
        
def normalize_data(X_train, X_cv):
    scaler = preprocessing.StandardScaler()
    scaler.fit(X_train)
    X_train = scaler.transform(X_train)
    X_cv = scaler.transform(X_cv)
    return X_train, X_cv


def train_classifier(classifier, data, normalize=False):
    X_train = data.X_train
    y_train = data.y_train
    X_cv = data.X_cv
    y_cv = data.y_cv
    if normalize:
        X_train, X_cv = normalize_data(X_train, X_cv)
    print( "Training ...")
    print( 'Dim', 'X', np.shape(X_train), 'y', np.shape(y_train), 'X_cv', np.shape(X_cv), 'y_cv', np.shape(y_cv))
    start = time.get_seconds()
    classifier.fit(X_train, y_train)
    print ("Scoring...")
    S, E = score_classifier_auc(classifier, X_cv, y_cv, data.y_classes)
    score = 0.5 * (S + E)

    elapsedSecs = time.get_seconds() - start
    print ("t=%ds score=%f" % (int(elapsedSecs), score))
    
    return {
        'classifier': classifier,
        'score': score,
        'S_auc': S,
        'E_auc': E
    }

class DownSampler():
    def __init__(self, load_core):
        self.load_core = load_core
        
    def apply(self, X):
        T = X.shape[-1]
        ratio = self.load_core.down_sampl_ratio
#         output = np.zeros((S, ratio))
        window_len = int(T/ratio)
#         if(window_len<2):
#             return X
#         for i in range(ratio):
#             output[:,i] = np.mean(X[:,i * window_len:(i+1) * window_len], axis=1)    
        output = X[...,0:window_len:T]
        return output
    
    
class NoChange():  
    def __init__(self, load_core):
        self.load_core = load_core
    def apply(self, X):
        return X   
        
class Normalize():
    def __init__(self, load_core):
        self.load_core = load_core
        
    def apply(self, X):
        y= (X-np.mean(X, axis=1)[:, np.newaxis])/np.sqrt(np.sum(X**2, axis=1)[:, np.newaxis])
        if(self.load_core.down_sampl_ratio is not None):
            y = DownSampler(self.load_core).apply(y)
        return y
    
class FFT():
    def __init__(self):
        return
        
    def apply(self, X_raw, load_core):
        win_length = int(np.ceil(load_core.welchs_win_len * load_core.sampling_freq))
        X = rolling_window(X_raw, win_length, int(np.ceil(load_core.welchs_stride * load_core.sampling_freq)))
        X = np.swapaxes(np.swapaxes(X, 0, 1), 1, 2)
        f_signal = rfft(X) 
        W = fftfreq(f_signal.shape[-1], d=1/load_core.sampling_freq)

#         f_signal = np.swapaxes(f_signal, 2, 3)
#         if(load_core.down_sampl_ratio is not None):
#             f_signal = DownSampler(load_core).apply(f_signal)
        conv_sizes = []
        all_sizess = np.zeros_like(W)
        for i in np.arange(len(load_core.freq_bands)):
            if(i>0):
                lowcut = load_core.freq_bands[i-1]
            else:
                lowcut = load_core.initial_freq_band
            highcut = load_core.freq_bands[i]
            sizess = np.where(W<highcut, np.ones_like(W), np.zeros_like(W))
            sizess = np.where(W<lowcut, np.zeros_like(W), sizess)
            all_sizess += sizess
            conv_sizes.append(int(np.sum(sizess)*f_signal.shape[-2]))
        in_FFT_W = f_signal[...,np.squeeze(np.argwhere(all_sizess==1))]
        FFT_W = np.reshape(in_FFT_W, (in_FFT_W.shape[0], in_FFT_W.shape[1], in_FFT_W.shape[2]*in_FFT_W.shape[3]))
#         W = np.tile(W,np.hstack((f_signal.shape[:-1],1)))
#         FFT_W = None        
#         for i in np.arange(len(load_core.freq_bands)):
#             if(i>0):
#                 lowcut = load_core.freq_bands[i-1]
#             else:
#                 lowcut = load_core.initial_freq_band
#             highcut = load_core.freq_bands[i]
# #             butter_bandpass_filter(data, lowcut, highcut, fs)
#             cut_f_signal = f_signal.copy()
# #             cut_f_signal = np.where(W<highcut, cut_f_signal,0 ) 
# #             cut_f_signal = np.where(W>=lowcut, cut_f_signal,0 ) 
#             cut_f_signal[ W >= highcut] = 0 # np.abs(W)
#             cut_f_signal[ W < lowcut] = 0
#             cut_f_signal = np.reshape(cut_f_signal, np.hstack((cut_f_signal.shape[:-2],np.multiply(cut_f_signal.shape[-2],cut_f_signal.shape[-1]))))# check again if correct ?????????????
#             if(load_core.down_sampl_ratio is not None):
#                 cut_f_signal = DownSampler(load_core).apply(cut_f_signal)
#             if(FFT_W is None):
#                 FFT_W = cut_f_signal
#             else:
#                 FFT_W = np.concatenate((FFT_W,cut_f_signal), axis=-1)
#             conv_sizes.append(cut_f_signal.shape[-1])
        return FFT_W, np.array(conv_sizes)
    
      
def data_convert(x, load_core):
    conversion_names = load_core.data_conversions #.split('+')
    y= None
    conv_sizes = None
    for i in range(len(conversion_names)):
#         exec("y.append(%s(load_core).apply(x))" % (conversion_names[i]) )
        conv, new_conv_sizes = conversion_names[i].apply(x, load_core)
        y = conv if y is None else np.concatenate((y,conv),axis=-1)
        conv_sizes = new_conv_sizes if conv_sizes is None else np.hstack((conv_sizes, new_conv_sizes))
#     yy=None
#     for i in range(len(conversion_names)):
#         yy=y[i] if yy is None else np.concatenate((y[i],yy),axis=1)
    
    return np.array(y), conv_sizes

class Slice:
    """
    Take a slice of the data on the last axis.
    e.g. Slice(1, 48) works like a normal python slice, that is 1-47 will be taken
    """
    def __init__(self, start, end=None):
        self.start = start
        self.end = end

    def get_name(self):
        return "slice%d%s" % (self.start, '-%d' % self.end if self.end is not None else '')

    def apply(self, data, meta=None):
        s = [slice(None),] * data.ndim
        s[-1] = slice(self.start, self.end)
        return data[s]

def to_np_array(X):
    if isinstance(X[0], np.ndarray):
        # return np.vstack(X)
        out = np.empty([len(X)] + list(X[0].shape), dtype=X[0].dtype)
        for i, x in enumerate(X):
            out[i] = x
        return out

    return np.array(X)


             
def windowing_data(input_data, seizure_start_time_offsets, seizure_lengths, load_Core):
    S,T = input_data.shape
#     feature_extraction.graphL_core.num_nodes = S
    sampling_freq = load_Core.sampling_freq
    if(load_Core.num_windows is not None):
        win_len_sec = T/(sampling_freq * load_Core.num_windows)
        stride_sec = win_len_sec
    else:
        win_len_sec = 2.5
        stride_sec = 1.5  
        
    seizure_start_time_offsets *= sampling_freq
    seizure_lengths *= sampling_freq
    win_len = int(np.ceil(win_len_sec * sampling_freq))
    stride = int(np.ceil(stride_sec * sampling_freq))
    X = rolling_window(input_data, win_len, stride) # np.swapaxes(, 0, 1) # np.lib.stride_tricks.as_strided(input_data, strides = st, shape = (input_data.shape[1] - w + 1, w))[0::o]
    if(load_Core.down_sampl_ratio is not None):
        X = DownSampler(load_Core).apply(X)
    X, conv_sizes = data_convert(X, load_Core) # X
    intervals_with_stride = np.arange(0, T - win_len, stride) # rolling_window(np.arange(T)[np.newaxis,:], win_len, stride) # 
    num_windows = len(intervals_with_stride)
    print('    win_len_sec: %f , num_windows: %d' % (win_len_sec, num_windows))
    y = np.zeros((num_windows,))
    flag_ictal = False
    y_detection = 1 if load_Core.detection_flag else 0
    def state_gen(y, win_ind):
        if(len(load_Core.state_win_lengths)<1):
            return y
        state_counter = 2 if load_Core.detection_flag else 1
        num_winds = list(np.ceil(np.array(load_Core.state_win_lengths)/win_len_sec).astype(np.int))
        end_ind = win_ind
        for le in num_winds:
            start_ind = np.max((0,end_ind-le))
            y[start_ind:end_ind] = state_counter
            state_counter +=1
            end_ind = start_ind
            if(end_ind<=0):
                break
        return y
        
    if(seizure_start_time_offsets>=0 and seizure_lengths>=0):
        for win_ind in range(num_windows):
            w = intervals_with_stride[win_ind]
            if((seizure_start_time_offsets<w + win_len) and (seizure_start_time_offsets + seizure_lengths >w)):
                y[win_ind] = y_detection
                if(not flag_ictal):
                    flag_ictal = True
                    y = state_gen(y, win_ind)
                        
    dim = X.shape[2]
    return X, y, S, dim, conv_sizes

    
