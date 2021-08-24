from types import MethodType
from flask import Flask, jsonify, request
from flask_redis import FlaskRedis
from kubernetes import client, config
import os

config.load_incluster_config()
v1 = client.CoreV1Api()
app = Flask(__name__)
app.config["REDIS_URL"] = os.getenv("REDIS_URL")
redis_client = FlaskRedis(app)
global_budget = 150.0


@app.route('/budget/<ns>/report',methods = ['POST'])
def budget_repot(ns):
    report = request.json
    usage = float(report["usage_factor"]) 
    pod_name = report["pod_name"]
    terminate = False
    resp = v1.read_namespaced_pod(name=pod_name,namespace=ns)
    container_statuses = list(resp.status.container_statuses)
    del container_statuses[[i for i,x in enumerate(container_statuses) if x.name == "gpu-sidecar"][0]]
    for container in container_statuses:
        if container.state.running == None:
            terminate = True
        else:
            terminate = False
            break
    if not terminate:
        if redis_client.exists(f"usage/{ns}"):
            
            remaining_budget = float(redis_client.get(f"usage/{ns}")) - usage 
            if remaining_budget <=  0.0:
                remaining_budget = 0.0
                v1.delete_namespaced_pod(pod_name, ns, async_req=True)
            redis_client.set(f"usage/{ns}",remaining_budget)
        else:
            redis_client.set(f"usage/{ns}", global_budget-usage)
    app.logger.error(f"Key usage/{ns} is set")
    return jsonify({"terminate": terminate})

@app.route('/budget/<ns>',methods = ['GET'])
def return_budget(ns):
    if redis_client.exists(f"usage/{ns}"):
        budget = float(redis_client.get(f"usage/{ns}"))
        if budget > 0:
            resp = {"budget_available" : True, "budget": global_budget, "budget_remaining": budget }
        else:
            resp = {"budget_available" : False, "budget": global_budget, "budget_remaining": budget }
    else:
        resp = {"budget_available" : True, "budget": global_budget, "budget_remaining": global_budget }
    return jsonify(resp)

@app.route('/budget/<ns>/increase',methods = ['POST'])
def íncrease_budget(ns):
    if redis_client.exists(f"usage/{ns}"):
        budget = float(redis_client.get(f"usage/{ns}"))
        if budget > 0:
            resp = {"budgetAvailable" : True, "budget": global_budget, "budget_remaining": budget }
        else:
            resp = {"budgetAvailable" : False, "budget": global_budget, "budget_remaining": budget }
    else:
        resp = {"budget_available" : True, "budget": global_budget, "budget_remaining": global_budget }
    return jsonify(resp)
