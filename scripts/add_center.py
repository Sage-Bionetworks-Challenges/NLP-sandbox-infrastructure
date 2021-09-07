"""Adds a center's dataset

1. Create center bot?
2. Create internal queues
3. Add to configuration table
4. Make sure orchestrator configured to accept submissions from
internal queues {"queue_id": "syn25582656"...}
5. Add to submission view
"""
import argparse

import challengeutils
import pandas as pd
import synapseclient


# List of annotator types
ANNOTATORS = ["Id", "Date", "Covid Symptom", "Contact", "Person Name", "Location"]


def create_evaluation_queues(syn, center, annotator_types):
    queue_mapping = {}
    for annotator_type in annotator_types:
        queue_name = f"{center} - {annotator_type} Annotator"
        queue_ent = synapseclient.Evaluation(
            name=queue_name,
            contentSource="syn22277123"
        )
        queue_ent = syn.store(queue_ent)
        challengeutils.permissions.set_evaluation_permissions(
            syn=syn,
            evaluation=queue_ent,
            principalid=3413389,
            permission_level="admin"
        )
        queue_mapping[queue_name] = queue_ent.id
    return queue_mapping


def main():
    # Build cli
    parser = argparse.ArgumentParser(description='Add center')
    parser.add_argument('center', type=str, help="Center to add")
    args = parser.parse_args()

    center = args.center
    syn = synapseclient.login()

    # Create evaluation queues for internal queue
    queue_mapping = create_evaluation_queues(
        syn=syn,
        center=center,
        annotator_types=ANNOTATORS
    )

    # Create submission view
    view_columns = list(syn.getTableColumns("syn25582644"))
    submission_view_ent = synapseclient.SubmissionViewSchema(
        name=center,
        parent="syn22277124",
        scopes=list(queue_mapping.values()),
        columns=view_columns,
        addAnnotationColumns=False,
        addDefaultViewColumns=False
    )
    submission_view_ent = syn.store(submission_view_ent)

    # Update queue config
    queue_config_syn_id = "syn25952454"
    queue_config = {
        "queue_name": list(queue_mapping.keys()),
        "queue_id": list(queue_mapping.values()),
        "center": [center]*len(queue_mapping),
        "submission_viewid": [submission_view_ent.id]* len(queue_mapping)
    }
    queue_config_df = pd.DataFrame(queue_config)
    syn.store(synapseclient.Table(queue_config_syn_id, queue_config_df))


if __name__ == "__main__":
    main()
