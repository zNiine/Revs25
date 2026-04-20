#!/usr/bin/env python3
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow.keras import layers, Model, regularizers
from tensorflow.keras.optimizers import Adam
import itertools

# 1) Load data and compute Tilt_deg
def clock_to_degrees(clock_str):
    try:
        h, m = map(int, clock_str.split(':'))
    except:
        return np.nan
    return (90 - ((h % 12) + m/60.0)*30) % 360

raw = pd.read_csv('data.csv')
raw['Tilt_deg'] = raw['Tilt'].apply(clock_to_degrees)

# 1a) Filter pitchers with >=24 total pitches
pitcher_counts = raw.groupby('PitcherId').size()
eligible = pitcher_counts[pitcher_counts >= 24].index
raw = raw[raw['PitcherId'].isin(eligible)].reset_index(drop=True)

# 2) Factorize IDs and Top/Bottom
pitcher_codes, pitcher_vals = pd.factorize(raw['PitcherId'])
batter_codes,  batter_vals  = pd.factorize(raw['BatterId'])
raw['Pitcher_code'] = pitcher_codes
raw['Batter_code']  = batter_codes
raw['TopBottom'] = (raw['Top/Bottom']=='Top').astype(int)

# 3) Compute pitcher & batter profiles
NUM_BASE = ['RelSpeed','SpinRate','Extension',
            'PlateLocHeight','PlateLocSide',
            'VertBreak','HorzBreak']
pit_profile = raw.groupby('Pitcher_code')[NUM_BASE].mean()
bat_profile = raw.groupby('Batter_code')[['ExitSpeed','Angle']].mean()

# 4) Build PA_key and labels with count & state
raw['PA_key'] = raw['GameID'].astype(str) + '_' + raw['Batter'].astype(str) + '_' + raw['PAofInning'].astype(str)
raw['walk'] = (raw['KorBB']=='BB').astype(int)
raw['k']    = (raw['KorBB']=='K').astype(int)
raw['hit']  = raw['PlayResult'].isin(['Single','Double','Triple','HomeRun']).astype(int)
raw['out']  = ((raw['PlayResult']=='Out')|(raw['PlayResult']=='Error')).astype(int)
# take last pitch per PA, capturing Top/Bottom too
labels = (
    raw.sort_values(['PA_key','PitchofPA'])
       .groupby('PA_key', as_index=False)
       .tail(1)[
         ['PA_key','walk','k','hit','out',
          'Pitcher_code','Batter_code',
          'Balls','Strikes','Outs',
          'PAofInning','TopBottom']
       ]
)
labels.rename(columns={'PAofInning':'Inning'}, inplace=True)
# now labels includes TopBottom

# 5) One-hot pitch type + aggregate per-PA features + aggregate per-PA features
ptype = pd.get_dummies(raw['AutoPitchType'], prefix='ptype')
raw = pd.concat([raw, ptype], axis=1)
NUM = ['RelSpeed','SpinRate','Extension','PlateLocHeight','PlateLocSide',
       'VertBreak','HorzBreak','ExitSpeed','Angle','SpinAxis','Tilt_deg'] + ptype.columns.tolist()
agg = {c:'mean' for c in NUM}
agg['PitchofPA'] = 'count'
pa = raw.groupby('PA_key').agg(agg).rename(columns={'PitchofPA':'PA_length'}).reset_index()
pa = pa.merge(labels, on='PA_key', how='inner')
# merge profiles
pa = pa.join(pit_profile, on='Pitcher_code', rsuffix='_pit')
pa = pa.join(bat_profile, on='Batter_code', rsuffix='_bat')

# 6) Prepare data
# Outcome matrix
y = pa[['walk','k','hit','out']].values
# Feature list with added counts and state
FEATURES = NUM + NUM_BASE + ['ExitSpeed_bat','Angle_bat','Balls','Strikes','Outs','PA_length','Inning','TopBottom']
X_num = pa[FEATURES].fillna(pa[FEATURES].median())
X_num = StandardScaler().fit_transform(X_num)
X = {
    'numeric': X_num.astype('float32'),
    'pitcher_id': pa.Pitcher_code.values.astype('int32'),
    'batter_id': pa.Batter_code.values.astype('int32')
}
train_idx, val_idx = train_test_split(np.arange(len(pa)), test_size=0.2, random_state=42)
def make_ds(idx):
    ds = tf.data.Dataset.from_tensor_slices((
        {k:v[idx] for k,v in X.items()},
        y[idx].astype('float32')
    ))
    return ds.shuffle(len(idx)).batch(512).prefetch(tf.data.AUTOTUNE)
train_ds = make_ds(train_idx)
val_ds   = make_ds(val_idx)

# 7) Build model with residuals, batchnorm, dropout, lower LR, clip
Dim = X_num.shape[1]
n_p = pa.Pitcher_code.nunique()
n_b = pa.Batter_code.nunique()
num_in = layers.Input((Dim,), name='numeric')
pid_in = layers.Input((), dtype='int32', name='pitcher_id')
bid_in = layers.Input((), dtype='int32', name='batter_id')
p_emb = layers.Embedding(n_p, 128)(pid_in)
b_emb = layers.Embedding(n_b, 128)(bid_in)
flat = layers.Concatenate()([num_in, layers.Flatten()(p_emb), layers.Flatten()(b_emb)])
from tensorflow.keras.regularizers import l2

def res_block(x, units):
    y = layers.Dense(units, kernel_regularizer=l2(1e-5))(x)
    y = layers.BatchNormalization()(y)
    y = layers.Activation('relu')(y)
    y = layers.Dropout(0.3)(y)
    y = layers.Dense(units, kernel_regularizer=l2(1e-5))(y)
    y = layers.BatchNormalization()(y)
    out = layers.Add()([x, y])
    return layers.Activation('relu')(out)

x = layers.Dense(256, kernel_regularizer=l2(1e-5))(flat)
x = layers.BatchNormalization()(x)
x = layers.Activation('relu')(x)
x = layers.Dropout(0.3)(x)
for units in [256,256,256]: x = res_block(x, units)
out = layers.Dense(4, activation='softmax', name='outcome')(x)
model = Model([num_in,pid_in,bid_in], out)
optimizer = Adam(learning_rate=1e-4, clipnorm=1.0)
model.compile(optimizer=optimizer, loss='categorical_crossentropy', metrics=['accuracy'])
model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=50,
    callbacks=[
        tf.keras.callbacks.EarlyStopping(monitor='val_accuracy', patience=5, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor='val_accuracy', factor=0.5, patience=3)
    ]
)

# 8) Predict full Cartesian product using baseline numeric mean and embeddings only
pairs = pd.DataFrame(list(itertools.product(pa.Pitcher_code.unique(), pa.Batter_code.unique())), columns=['Pitcher_code','Batter_code'])
# baseline numeric features = mean of X_num
baseline = X_num.mean(axis=0).reshape(1, -1)
# create full numeric input array
num_inp = np.repeat(baseline, len(pairs), axis=0).astype('float32')
ids_p = pairs.Pitcher_code.values.astype('int32')
ids_b = pairs.Batter_code.values.astype('int32')
# build dataset
inf_ds = tf.data.Dataset.from_tensor_slices((
    {'numeric': num_inp, 'pitcher_id': ids_p, 'batter_id': ids_b}
)).batch(1024)
# predict
pred = model.predict(inf_ds)
# unpack probabilities
pairs['walk_pct'], pairs['k_pct'], pairs['hit_pct'], pairs['out_pct'] = pred.T
# map back to original IDs
pairs['PitcherId'] = pairs.Pitcher_code.map(lambda c: pitcher_vals[c])
pairs['BatterId'] = pairs.Batter_code.map(lambda c: batter_vals[c])
# save
pairs[['PitcherId','BatterId','walk_pct','k_pct','hit_pct','out_pct']].to_csv('all_matchups_predicted_softmax.csv', index=False)
print('Saved', len(pairs), 'rows.')
