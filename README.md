# GPUSharing

This implementation adresses a fundamental limitation of GPUs in Kubernetes wherein a physical GPU can only be allocated to a pod exclusively.
Currently there is no out of the box feature for sharing a GPU across multiple pods (See [this](https://github.com/kubernetes/kubernetes/issues/52757) open kubernetes issue since 2017).
Third-party solutions such as [gpu-manager](https://github.com/tkestack/gpu-manager) (GaiaGPU) or [kubeshare](https://github.com/NTHU-LSALAB/KubeShare) implement fractional pod allocation / isolation by intercepting CUDA calls.

Kubernetes GPUSharing uses [gpu-manager](https://github.com/tkestack/gpu-manager) under the hood, adding several features on top to provide feasible sharing of GPU devices in production kubernetes clusters.
Especially clusters with a large userbase profit from GPU sharing (Reduced waiting time, increased GPU utilization).

_Warning_: This repo is in a POC stage. Feel free to evaluate and contribute.

## Features

- Allows fractional GPU allocations (E.g. 1/3 of a phsyical GPU) to pods through [gpu-manager](https://github.com/tkestack/gpu-manager)

- Enforcement of GPU Request Governance:
    - Deny malformed GPU device requests (E.g. resource request must 1<tencent.com/vcuda-core<100 || n * 100)
    - Automated setting of required gpu-manager-specific annotation tags
- Budgeting of GPU Resources:
    - Global budget is assigned to every namespace
    - While in budget, the pods in a namespace run with default priority
    - When out of budget, a pod is started with reduced priority, thus evicted in favor of in-budget pods
    - GPU quota implemented using default kubernetes [ResourceQuotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- Invisible to users and applications. Just state the fractional GPU resource request in the pod/job/deployment specification (See Example)


## Example

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: mnist-case
spec:
  containers:
  - image: localhost:5000/usecase/mnist:latest
    name: nvidia
    resources:
      limits:
        tencent.com/vcuda-core: 50      # 50% of a GPU
        tencent.com/vcuda-memory: 15    # 15 * 256MB of VRAM
```

## Architecture

### Overall Architecture

![gpuss_overview](https://user-images.githubusercontent.com/23240158/130106094-409a0e58-d60d-46d5-8edb-ce24d45df722.png)


### Admission Flow

![gpu-admission-webhook](https://user-images.githubusercontent.com/23240158/130364500-875fa9b3-286f-434c-8581-4706b1b7cfd1.png)


### GPU Sidecar

Is a [sidecar container](https://kubernetes.io/docs/concepts/workloads/pods/#how-pods-manage-multiple-containers) that is injected into the pods using GPU resources to report GPU budget consumption to GPU timekeeper.

### GPU Timekeeper

Is a service that keeps track of per user (identified per namespace) consumption of GPU resources.


### Admission Webhook

Is a Webservice that sits in the kubernetes admission flow to validate GPU request governance, assign priorities to pods and inject sidecar containers.

---

## Getting Started

### Prerequisites

* Tested with Kubernetes >v1.20
* Only Nvidia GPUs supported
* Setup [gpu-manager](https://github.com/tkestack/gpu-manager), including [gpu-admission](https://github.com/tkestack/gpu-admission)

### Quickstart

For Quickstart use provided yaml files in `deployment` using images on Dockerhub:

```bash
kubectl create -f deployment/
```

### Configuration

Currently the solution must be configured in code.
Configuration outside the code is added shortly.

Configuration of quota in yaml:
```
deployment/quotas.yaml
```
Quota must also be set in code for correct calculation of budget consumption:
```
src/gpu-admission-webhook/src/app.py
```
Configure global per namespace GPU budget in minutes in:
```
src/gpu-timekeeper/app/main.py
```


---

## License

Copyright (c) 2021 Timo Zerrer and others


Licensed under the Apache License, Version 2.0 (the "License"); 
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.