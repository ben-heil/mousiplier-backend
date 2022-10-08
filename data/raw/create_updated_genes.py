#!/usr/bin/env python3

"""
This script reads a gene information file then prints out gene synonyms.
The output will be used as the input file of the
management command `update_gene_names_aliases.py`.
"""

import csv

gene_annotations = dict()


def read_gene_annotation():
    """
    Read in an RPT file of mouse gene annotations.

    Column number 6 contains a gene symbol, while column 11 contains its
    synonyms (if any), delineated by '|'.

    Returns a dict whose key is a gene symbol, and value is a list of
    synonyms

    NOTE: This function should be called before read_errata().
    """

    gene_annotation_src = 'mouse_gene_annotations.tsv'
    with open(gene_annotation_src) as fh:
        reader = csv.reader(fh, delimiter='\t', quotechar='"')
        for line_num, row in enumerate(reader, start=1):
            if line_num == 1 or row[0].startswith('#'):
                continue

            gene_symbol = row[6]
            synonyms = row[11].split('|')
            gene_annotations[gene_symbol] = synonyms

if __name__ == '__main__':
    read_gene_annotation()

    # Merge pao1_to_pa14 and gene_annotations
    print("#standard_name", "synonyms", sep='\t')
    for gene_symbol, synonyms in gene_annotations.items():
        synonyms = ' '.join(synonyms).strip()
        print(gene_symbol, synonyms, sep='\t')
