"""
This management command imports experiments, samples/annotations data
from an input file and loads them into the corresponding tables in
backend database.
"""

import logging
import pandas as pd
from operator import itemgetter
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from analyses.models import Experiment, Sample, SampleAnnotation, AnnotationType

JSON_CACHE_FILE_NAME = 'json_cache.p'


class Command(BaseCommand):
    help = (
        'Imports data to initialize the database with Experiment, Sample, and '
        'SampleAnnotation records.'
    )

    def add_arguments(self, parser):
        parser.add_argument('annotation_file', type=open)

    def handle(self, **options):
        try:
            with transaction.atomic():
                import_data(options['annotation_file'])
            self.stdout.write(
                self.style.SUCCESS("Experiments and samples imported successfully")
            )
        except Exception as e:
            raise CommandError(
                "Experiment/sample/annotation import error: import_data "
                "threw an exception:\n%s" % e
            )


def import_data(annotation_fh, dir_name=None):
    """
    Import experiments, samples, and annotations data to initialize the backend
    database. We assume that we are starting with an empty database, so this
    will fail if any existing data are found that conflict with what is being
    imported.

    `annotation_fh`: a file handle open to the beginning of a UTF-8 plain text
    format of the annotated spreadsheet data.

    `dir_name`: a directory for storing .sdrf.txt files to be downloaded by
    get_pseudo_sdrf.download_sdrf_to_dir(). If no `dir_name` is supplied, the
    current working directory will be used. This collection of files constitutes
    an authoritative reference for what samples comprise each experiment. In
    addition, a cache containing a record of the JSON data retrieved from
    ArrayExpress will be saved here.

    This function will raise errors if it is unable to complete successfully,
    and it will exit with no error if it succeeds in initializing the database.
    """
    ## We're loading our experiments info from a metadata file so we don't
    ## need to query arrayexpress
    #if not dir_name: dir_name = os.getcwd()
    #if not os.path.isdir(dir_name):
    #    os.mkdir(dir_name)
    #ss = gs.Spreadsheet()
    #ss.parse_txt_file(annotation_fh)

    ## download all experiment attributes from ArrayExpress and create an
    ## Experiment in the database for each matching experiment found in the
    ## annotation spreadsheet. Raise an error if any annotated experiment
    ## cannot be found in the data retrieved from ArrayExpress.
    #ae_retriever = gp.AERetriever(
    #    ae_url=gp._AEURL_EXPERIMENTS,
    #    cache_file_name=os.path.join(dir_name, JSON_CACHE_FILE_NAME)
    #)
    #ae_experiments = ae_retriever.ae_json_to_experiment_text()
    #annotated_experiments = ss.get_experiment_ids()
    ## we can fail fast by checking for missing experiments before we start
    #missing_experiments = (
    #    frozenset(annotated_experiments) -
    #    frozenset([e['accession'] for e in ae_experiments])
    #)
    #if missing_experiments:
    #    msg= "The following annotated experiments are missing from ArrayExpress: "
    #    raise RuntimeError(msg + "[{:s}]".format(', '.join(missing_experiments)))

    # nothing missing, so proceed with importing!
    recount_metadata = pd.read_csv(annotation_fh, sep='\t')
    experiment_info = recount_metadata[['study', 'sra.study_title', 'sra.study_abstract']]
    experiment_info = experiment_info.drop_duplicates()

    # Build a dataframe with one experiment per line by calling groupby on the
    # metadata and returning only exp-specific fields

    for _, row in experiment_info.iterrows():
        # Experiment create expects an accession, a name, a description,
        # and sample info
        row_info = {}
        row_info['accession'] = row['study']
        row_info['name'] = row['sra.study_title']
        row_info['description'] = row['sra.study_abstract']

        # There's a samples_info field in experiment objects, but I'm not sure
        # what it is or if it's used for anything. I'll leave it out for now
        # row_info['samples_info'] = pass

        Experiment.objects.create(**row_info)

    # now that we have database records for every Experiment, we walk through
    # the metadata dataframe and create records for Samples, linking each
    # to one or more Experiment(s) and creating a set of SampleAnnotations for
    # each as we go.
    mismatches = {}  # mismatches indexed by sample and experiment ids
    for _, r in recount_metadata.iterrows():
        row_experiment = Experiment.objects.get(accession=r['study'])

        # This may break something since adage listed all the CEL files each
        # experiment came from. However, all our data comes from the Recount3
        # compendium
        ml_data_source = r['external_id']
        if ml_data_source == '':
            ml_data_source = None
        row_sample, created = Sample.objects.get_or_create(
                name=r['external_id'], ml_data_source=ml_data_source)
        row_experiment.sample_set.add(row_sample)
        annotations = dict(
            (k, v) for k, v in r.to_dict().items() if k in (
                'sra.sample_description', 'sra.design_description',
                'sra.sample_attributes', 'sra.sample_name'
            )
        )
        if created:
            # a new sample was created so we need new annotations for it
            SampleAnnotation.objects.create_from_dict(row_sample, annotations)
        else:
            # sample was already present, so check if our annotations match
            existing_annotation_dict = SampleAnnotation.objects.get_as_dict(
                    sample=row_sample)
            for k, v in annotations.items():
                if not v:
                    # there is nothing to do if our value is blank
                    continue
                if k not in existing_annotation_dict:
                    # add a blank value to existing_annotation_dict to signal
                    # that this annotation needs to be added
                    existing_annotation_dict[k] = ""
                if existing_annotation_dict[k] != v:
                    # In this section, we automatically handle several minor
                    # data inconsistencies in the manually-generated annotation
                    # spreadsheet and report the rest for follow-up
                    if existing_annotation_dict[k] == "" and v != "":
                        # data trump emptiness: update the existing annotation
                        k_type, _ = AnnotationType.objects.get_or_create(
                                typename=k)
                        existing_annotation, _ = \
                            SampleAnnotation.objects.get_or_create(
                                annotation_type=k_type, sample=row_sample)
                        existing_annotation.text = v
                        existing_annotation.save()
                        continue
                    elif existing_annotation_dict[k] != "" and v == "":
                        # all okay here: nothing new to add.
                        continue
                    elif existing_annotation_dict[k].lower() == v.lower():
                        # don't care about minor differences in case
                        continue
                    elif existing_annotation_dict[k].lower().startswith(
                            v.lower()):
                        # nothing new to add (new annotation is a subset of
                        # what's there already)
                        continue
                    elif v.lower().startswith(
                            existing_annotation_dict[k].lower()):
                        # let's take the longer explanation (new annotation is
                        # a strict superset of what was provided already)
                        k_type = AnnotationType.objects.get(typename=k)
                        existing_annotation = SampleAnnotation.objects.get(
                                annotation_type=k_type, sample=row_sample)
                        existing_annotation.text = v
                        existing_annotation.save()
                        continue
                    # We organize our lists of mismatched fields by `sample`
                    # and the pair of experiments with conflicting annotations
                    # so we can report them at the end.  Build the err_key as:
                    # (sample, experiment, existing_experiment)
                    existing_experiment = row_sample.\
                            experiments.exclude(accession=r.accession)[0]
                    err_key = (
                        r.sample,
                        r.accession,
                        existing_experiment.accession
                    )
                    if err_key not in mismatches:
                        mismatches[err_key] = []
                    mismatches[err_key].append(k)
    if mismatches:
        # sort err_keys to match original spreadsheet order
        sorted_err_keys = sorted(mismatches.keys(), key=itemgetter(2, 0))
        warning_detail = []
        for key in sorted_err_keys:
            v = mismatches[key]
            warning_detail.append(
                ("Sample '{key[0]}' in experiment {key[1]} does not match"
                 " experiment {key[2]}. (Check fields: {check})"
                 ).format(
                    key=key, check=', '.join(v),
                   )
            )
        logging.warn(
            "Annotation mismatches found:\n{}".format(
                '\n'.join(warning_detail)
            )
        )
        raise RuntimeError(
            f'Annotation mismatches found. Total: {len(mismatches)} samples'
        )
