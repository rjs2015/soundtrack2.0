import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def prepare_data(df, category, resample=False, remove_vars='duration_ms'):
    '''
    Prepare data for model training.
    Optionally resample the song data so that the binary flags are balanced
    '''
    data = df
    
    if resample:
        in_category = df[df['category'] == category]
        other_category = df[df['category'] != category].sample(len(in_category))    
        data =  pd.concat([in_category, other_category])

        return data.loc[:, data.dtypes != 'object'].drop(remove_vars, axis=1), (data['category'] == category)


def pr_curve(true, pred, label, digit_prec=2):
    '''Plot the precision/recall curves based on vectors of true and predicted values'''
    thresholds = np.unique(np.round(pred, digit_prec))
    num_thresholds = len(thresholds)
    tp_vec = np.zeros(num_thresholds)
    fp_vec = np.zeros(num_thresholds)
    fn_vec = np.zeros(num_thresholds)

    for idx in range(num_thresholds):
        threshold = thresholds[idx]
        tp_vec[idx] = sum(true[pred>=threshold])
        fp_vec[idx] = sum(1-true[pred>=threshold])
        fn_vec[idx] = sum(true[pred<threshold])
    recall = tp_vec/(tp_vec + fn_vec)
    precision = tp_vec/(tp_vec + fp_vec)
    plt.plot(precision, recall, label=label)
    plt.axis([0, 1, 0, 1])
    plt.xlabel("precision")
    plt.ylabel("recall")
    return (recall, precision, thresholds)

def top_score_string(x):
    return '{top}: {score}'.format(top=np.argmax(x), score=np.round(max(x), 3))
