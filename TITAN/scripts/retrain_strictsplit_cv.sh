NAME=titanData_strictsplit_nocdr3
DATAFOLDER=TITAN/data/strict_split_nocdr3/
TCRFILE=TITAN/data/tcr.csv
EPFILE=TITAN/data/epitopes.csv
SAVEFOLDER=TITAN/models/$NAME
PARAMS=TITAN/params/params_training_AACDR3_paper.json

mkdir -p $SAVEFOLDER

for CV in {0..9}; do
  mkdir -p $SAVEFOLDER/cv$CV
  python TITAN/scripts/flexible_training.py $DATAFOLDER/fold$CV/train+covid.csv $DATAFOLDER/fold$CV/test+covid.csv \
    $TCRFILE $EPFILE $SAVEFOLDER/cv$CV/ $PARAMS "${NAME}_${CV}" bimodal_mca 2>&1 | tee -a $SAVEFOLDER/cv$CV.log
done
