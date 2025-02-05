
export PROJECT_ROOT='./ImRex'

python ${PROJECT_ROOT}/src/scripts/train/scenario_padding.py \
--batch_size 32 \
--epochs 20 \
--cv "epitope_grouped" \
--n_folds 5 \
--full_dataset_path "${PROJECT_ROOT}/data/interim/vdjdb-2019-08-08/vdjdb-human_scrambled_eps.csv" \
--min_length_cdr3 10 \
--max_length_cdr3 20 \
--min_length_epitope 8 \
--max_length_epitope 11 \
--features "hydrophob,isoelectric,mass,hydrophil" \
--operator "absdiff" \
--data_path "${PROJECT_ROOT}/data/interim/vdjdb-2019-08-08/vdjdb-human-trb-mhci-no10x-size-down400_pdb_no_cdr3_dup_scrambled_eps.csv" \
--model model_padded \
--depth1_1 128 \
--depth1_2 64 \
--depth2_1 128 \
--depth2_2 64 \
--activation_function_conv "relu" \
--activation_function_dense "relu" \
--dropout_conv 0.25 \
--learning_rate 0.0001 \
--regularization 0.01 \
--optimizer rmsprop \
--name "scrambled_eps"
