import base64
import copy
import http
import json
import random
import logging
from typing import ValuesView
import requests
import jsonpatch
import math
from flask import Flask, jsonify, request
from kubernetes import client, config
import time

app = Flask(__name__)
config.load_incluster_config()


# TO-DO: move this to env vars
quota_gpu_mem = 15
quota_gpu_core = 50

@app.route("/validate", methods=["POST"])
def validate():
    allowed = True
    try:
        for container_spec in request.json["request"]["object"]["spec"]["containers"]:
            if "env" in container_spec:
                allowed = False
    except KeyError:
        pass
    return jsonify(
        {
            "response": {
                "allowed": allowed,
                "uid": request.json["request"]["uid"],
                "status": {"message": "env keys are prohibited"},
            }
        }
    )

def pass_admissionreview(request_uid,warnings = ["Approved"]):
    return jsonify(
        {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "allowed": True,
                "uid": request_uid,
            }
        }
    )

def patch_admissionreview(request_uid,spec, modified_spec,warnings = ["Approved with patch" ]):
    patch = jsonpatch.JsonPatch.from_diff(spec, modified_spec)
    return jsonify(
        {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "allowed": True,
                "uid": request_uid,
                "patchType": "JSONPatch",
                "patch": base64.b64encode(str(patch).encode()).decode(),
            }
        }
    )


def reject_admissionreview(request_uid, status = "Rejected"):
    return jsonify(
        {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "allowed": False,
                "uid": request_uid,
                "status": {
                    "code": 400,
                    "message": status
                    }
            }
        }
    ) 

def validate_limits_on_pod(modified_spec,container,cid, patch_required, ns):
    modified_spec["metadata"]["annotations"] = {
    "tencent.com/vcuda-core-limit" : container["resources"]["limits"]["tencent.com/vcuda-core"]
    }
    r = requests.get('http://gpu-timekeeper.kube-system/budget/' + ns)
    rj = r.json()
    if rj["budget_available"]:
        modified_spec["spec"]["priorityClassName"] = "gpu-default-priority"
    else:
        modified_spec["spec"]["priorityClassName"] = "gpu-lower-priority"
    del modified_spec["spec"]["priority"]

    patch_required = True
    return modified_spec, patch_required 

def create_sidecar(container):
    consumption_factor = (
    ((float(container["resources"]["limits"]["tencent.com/vcuda-core"])/quota_gpu_core)+
    (float(container["resources"]["limits"]["tencent.com/vcuda-memory"])/quota_gpu_mem)) 
    )/ 2
    # TO-DO: Move Sidecar image def to ENV
    sidecar = {
    	"name": "gpu-sidecar",
		"image": "timozerrer/gpu-sidecar",
		"env": [{
		    "name": "NAMESPACE",
		    "valueFrom": {
                "fieldRef": {
                "fieldPath": "metadata.namespace"
                }
            }
			},
            {
		    "name": "CONSUMPTION_FACTOR",
		    "value": str(consumption_factor)
			},
            {
		    "name": "POD_NAME",
		    "valueFrom": {
                "fieldRef": {
                "fieldPath": "metadata.name"
                }
            }
			}]
    }
    return sidecar

@app.route("/mutate", methods=["POST"])
def mutate():
    app.logger.info('Received Mutating request')
    request_uid = request.json["request"]["uid"]
    spec = request.json["request"]["object"]
    modified_spec = copy.deepcopy(spec)
    patch_required = False
    # Identify object type
    if spec["kind"] == "Pod":
        for cid, container in enumerate(spec["spec"]["containers"]): # TO-DO: Validate using more than 1 container in a pod
            if "limits" in container["resources"]:
                if "tencent.com/vcuda-core" in container["resources"]["limits"] and \
                  "tencent.com/vcuda-memory" in container["resources"]["limits"]:
                    modified_spec, patch_required = validate_limits_on_pod(modified_spec,container,cid,patch_required, request.json["request"]["namespace"])
                    sidecar_exists = False
                    for _container in spec["spec"]["containers"]:
                        if _container["name"] == "gpu-sidecar":
                            sidecar_exists = True
                    if not sidecar_exists and modified_spec["spec"]["priorityClassName"] == "gpu-default-priority":
                        app.logger.info(modified_spec)
                        sidecar = create_sidecar(container )
                        modified_spec["spec"]["containers"].append(sidecar)
                    if patch_required:
                        return patch_admissionreview(request_uid,spec,modified_spec)
                    return pass_admissionreview(request_uid, ["Approved without changes"])
                elif "tencent.com/vcuda-core" in container["resources"]["limits"] or \
                  "tencent.com/vcuda-memory" in container["resources"]["limits"]:
                    app.logger.info('Rejecting')
                    return reject_admissionreview(request_uid,
                        "Must supply both tencent.com/vcuda-core AND tencent.com/vcuda-memory"
                    )
            else:
                return pass_admissionreview(request_uid)
    elif spec["kind"] == "Deployment":
        pass_admissionreview(request_uid)
    elif spec["kind"] == "Job":
        pass_admissionreview(request_uid)

    patch = jsonpatch.JsonPatch.from_diff(spec, modified_spec)
    return jsonify(
        {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "allowed": True,
                "uid": request.json["request"]["uid"]
            }
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return ("", http.HTTPStatus.NO_CONTENT)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)  # pragma: no cover
else:
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)