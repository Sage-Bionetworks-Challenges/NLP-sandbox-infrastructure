"""Run training synthetic docker models"""
import argparse
import json
import os

import docker


def remove_docker_container(container_name):
    """Remove docker container"""
    client = docker.from_env()
    try:
        cont = client.containers.get(container_name)
        cont.stop()
        cont.remove()
    except Exception:
        print("Unable to remove container")


def remove_docker_image(image_name):
    """Remove docker image"""
    client = docker.from_env()
    try:
        client.images.remove(image_name, force=True)
    except Exception:
        print("Unable to remove image")


def main(args):
    """Run docker model"""
    client = docker.from_env()
    invalid_reasons = []

    print("Get submission container")
    # Get container
    submissionid = args.submissionid
    container = client.containers.get(submissionid)
    # This obtains the ip of each docker container only accesible to other
    # docker containers on the same network
    # docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' container_name
    container_ip = container.attrs['NetworkSettings'][
        'Networks'
    ]['submission']['IPAddress']
    print(container_ip)
    api_url_map = {
        'date': "textDateAnnotations",
        'person': "textPersonNameAnnotations",
        'address': "textPhysicalAddressAnnotations"
    }
    annotator_client = "nlpsandbox/cli:edge"
    # validate that the root URL redirects to the service API endpoint
    # exec_cmd = ["curl", "-s", "-L", "-X", "GET",
    #             f"http://{container_ip}:8080"]
    exec_cmd = ["evaluate", "get-tool", '--annotator_host',
                f"http://{container_ip}:8080/api/v1"]
    try:
        # auto_remove doesn't work when being run with the orchestrator
        tool = client.containers.run(annotator_client, exec_cmd,
                                     name=f"{args.submissionid}_curl_1",
                                     network="submission", stderr=True)
                                        # auto_remove=True)
        # Remove \n, and change single quote to double quote
        tool_info = json.loads(
            tool.decode("utf-8").replace("\n", "").replace("'", '"')
        )
        print(tool_info)
    except Exception as err:
        # TODO: Potentially add in more info
        invalid_reasons.append(
            "API api/v1/tool endpoint not implemented or implemented "
            "incorrectly. Make sure correct tool object is returned."
        )
    remove_docker_container(f"{args.submissionid}_curl_1")
    # Check that tool api version is correct
    if tool_info['tool_api_version'] != args.schema_version:
        invalid_reasons.append(
            f"API api/v1/tool toolApiVersion is not {args.schema_version}"
        )
    # Check UI
    exec_cmd = ["evaluate", "check-url", '--url',
                f"http://{container_ip}:8080/api/v1/ui"]
    try:
        # auto_remove doesn't work when being run with the orchestrator
        client.containers.run(annotator_client, exec_cmd,
                              name=f"{args.submissionid}_curl_2",
                              network="submission", stderr=True)
                              # auto_remove=True)
    except Exception as err:
        invalid_reasons.append(
            ".../api/v1/ui not implemented or implemented incorrectly."
        )
    remove_docker_container(f"{args.submissionid}_curl_2")

    # validate that the note can be annotated by particular annotator
    example_note = [{
        "identifier": "awesome-note",
        "noteType": "loinc:LP29684-5",
        "patientId": "awesome-patient",
        "text": "On 12/26/2020, Ms. Chloe Price met with Dr. Prescott in \
            Seattle."
    }]
    with open("example_note.json", "w") as example_f:
        json.dump(example_note, example_f)

    # TODO: need to support other annotators once implemented
    exec_cmd = ["evaluate", "annotate-note", '--annotator_host',
                f"http://{container_ip}:8080/api/v1", '--note_json',
                '/example_note.json', '--annotator_type',
                args.annotator_type]

    volumes = {
        os.path.abspath("example_note.json"): {
            'bind': '/example_note.json',
            'mode': 'rw'
        }
    }
    try:
        example_post = client.containers.run(
            annotator_client, exec_cmd,
            volumes=volumes,
            name=f"{args.submissionid}_curl_2",
            network="submission", stderr=True,
            # auto_remove=True
        )
        example_dict = json.loads(
            example_post.decode("utf-8").replace("\n", "").replace("'", '"')
        )
        print(example_dict)
    except Exception as err:
        invalid_reasons.append(
            f"API /{api_url_map[args.annotator_type]} endpoint not implemented "
            "or implemented incorrectly.  Make sure correct Annotation "
            "object is annotated."
        )
    remove_docker_container(f"{args.submissionid}_curl_2")

    print("finished")
    print(invalid_reasons)
    # If there are no invalid reasons -> Validated
    if not invalid_reasons:
        prediction_file_status = "VALIDATED"
    else:
        prediction_file_status = "INVALID"
        # Try to remove the image if the service is invalid
        remove_docker_container(args.submissionid)
        remove_docker_image(container.image)

    result = {'submission_errors': "\n".join(invalid_reasons),
              'submission_status': prediction_file_status}
    with open(args.results, 'w') as file_o:
        file_o.write(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--submissionid", required=True,
                        help="Submission Id", type=str)
    parser.add_argument("-c", "--synapse_config", required=True,
                        help="credentials file")
    parser.add_argument("-r", "--results", required=True,
                        help="results file")
    parser.add_argument("-a", "--annotator_type", required=True,
                        help="Annotation Type")
    parser.add_argument(
        "--subset_data", required=True,
        help="The subset of data to validate reproducibility of notes."
    )
    parser.add_argument(
        "--schema_version", required=True,
        help="The API verison of the data node and annotator schemas."
    )
    args = parser.parse_args()
    main(args)
