#!/bin/bash
# set -e: exit at any error
# set -x: print out every command executed
set -e

# This script took ~33 minutes to populate a local Postgres database on
# Linux desktop in Greene Lab (~4 hours to populate an RDS instance).

# Get absolute paths based on current script's path
SCRIPT_DIR=$(dirname $0)
ABS_SCRIPT_DIR=$(cd ${SCRIPT_DIR}; pwd)  # absolute path of script dir
REPO_DIR=$(dirname ${ABS_SCRIPT_DIR})
PROJECT_DIR="${REPO_DIR}/adage"
DATA_DIR="${REPO_DIR}/data"
DIVIDER="-------------------------------------------------"

# Constants used in management commands
TAX_ID=10090
MODEL="Mousiplier"
PARTICIPATION_TYPE="Non-zero genes"

# Populate database
cd ${PROJECT_DIR}

date; echo "Creating new organism ..."
./manage.py create_or_update_organism \
	    --tax_id=${TAX_ID} \
	    --scientific_name="Mus musculus" \
	    --common_name="Mouse" \


## TODO can update this with an actual pointer to Entrez, MGI, and Alliance Genome, but I'm not really sure 
## What they do here or what format their URL is suppoed to be
#echo $DIVIDER; date; echo "Creating CrossRefDB ..."
#./manage.py create_or_update_xrdb \
#	    --name="Ensembl" \
#	    --URL="http://www.pseudomonas.com/getAnnotation.do?locusID=_REPL_"
#
echo $DIVIDER; date; echo "Importing gene_info ..."
./manage.py import_gene_info \
	  --filename="${DATA_DIR}/filtered_Mus_musculus.gene_info" \
	  --tax_id=${TAX_ID} \

echo $DIVIDER; date; echo "Importing gene_history ..."
./manage.py import_gene_history \
	    --filename="${DATA_DIR}/filtered_history_10090" \
	    --tax_id=${TAX_ID}

#echo $DIVIDER; date; echo "Importing updated genes ..."
#./manage.py import_updated_genes "${DATA_DIR}/updated_genes.tsv"

echo $DIVIDER; date; echo "Importing experiments and samples ..."
# The following command took ~4 minutes to import data to an RDS instance:
# TODO uncomment later; commenting to test other scripts
./manage.py import_experiments_samples "${DATA_DIR}/recount_metadata.tsv"

echo $DIVIDER; date; echo "Adding samples_info to each experiment ..."
./manage.py add_samples_info_to_experiment

echo $DIVIDER; date; echo "Adding simple machine learning model ..."
./manage.py create_or_update_ml_model "${DATA_DIR}/mousiplier_ml_model.yml"

echo $DIVIDER; date; echo "Importing sample-signature activity for simple ML model ..."
# The following command took ~TODO minutes to import sample-signature activity data to a local
# Postgres database on Linux desktop in Greene Lab (~ TODO hours to an RDS instance)
./manage.py import_sample_signature_activity \
	    --filename="${DATA_DIR}/mousiplier_sample_signature_activity.tsv" \
	    --ml_model="${MODEL}"

echo $DIVIDER; date; echo "Importing gene-gene network for simple ML model ..."
./manage.py import_gene_network \
	  --filename="${DATA_DIR}/mousiplier_gene_gene_network_cutoff_0.2.txt" \
	  --ml_model="${MODEL}"

echo $DIVIDER; date; echo "Creating new participation type ..."
./manage.py create_or_update_participation_type \
	    --name="${PARTICIPATION_TYPE}" \
	    --desc="PLIER uses an L1 penalty to zero out less-relevant genes. The participating genes are ones that have non-zero weights."

echo $DIVIDER; date; echo "Importing gene-signature participation data for simple ML model ..."
# The following command took ~TODO minutes to import gene-signature participation data to a local
# Postgres database on Linux desktop in Greene Lab (~TODO minutes to an RDS instance).
./manage.py import_gene_signature_participation \
	    --filename="${DATA_DIR}/mousiplier_gene_signature_participations.tsv" \
	    --ml_model="${MODEL}" \
	    --participation_type="${PARTICIPATION_TYPE}"

## Omitting this command to see what breaks; the expression data here is 40GB so we probably
## don't want to have to store it unless its critical
#echo $DIVIDER; date; echo "Importing gene-sample expression data ..."
## The following command took ~6 minutes to import gene-sample expression data to a local
## Postgres database on Linux in Greene Lab (~8 minutes to an RDS instance), with six
## warning messages:
##   * line #1: data_source in column #973 not found in database: JS-1B4.9.07.CEL
##   * line #1: data_source in column #974 not found in database: JS-A164.9.07.CEL
##   * line #1: data_source in column #975 not found in database: JS-A84.9.07.CEL
##   * line #1: data_source in column #976 not found in database: JS-G164.9.07.CEL
##   * line #1: data_source in column #977 not found in database: JS-G84.18.07.CEL
##   * line #1: data_source in column #978 not found in database: JS-T24.9.07.CEL
#./manage.py import_gene_sample_expression \
#	    --filename="${DATA_DIR}/gene_sample_expression.tsv" \
#	    --tax_id=${TAX_ID}

echo $DIVIDER; echo "Database populated successfully!"; date
