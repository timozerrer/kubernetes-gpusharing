import subprocess
import base64
import os
from pathlib import Path
from shutil import which
def generate_keys(service, namespace, directory="keys"):
    "Generate key material and configuration for Kubernetes admission controllers"

    if not which("openssl"):
        raise click.UsageError("Unable to detect the openssl CLI tool on the path")

    if not os.path.exists(directory):
        os.makedirs(directory)

    print("==> Generating CA")

    command = """openssl genrsa -out ca.key 2048
openssl req -x509 -new -nodes -key ca.key -days 100000 -out ca.crt -subj '/CN=admission_ca'"""

    subprocess.run(command, cwd=directory, shell=True, stderr=subprocess.DEVNULL)

    print("==> Creating configuration")

    with open(Path(directory) / "server.conf", "w") as f:
        f.write(
            """[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name
[req_distinguished_name]
[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth, serverAuth
"""
        )

    print("==> Generating private key and certificate")

    address = "{}.{}.svc".format(service, namespace)

    command = """openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/CN={}" -config server.conf
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 100000 -extensions v3_req -extfile server.conf""".format(
        address
    )

    subprocess.run(command, cwd=directory, shell=True, stderr=subprocess.DEVNULL)

    print("==> Key material generated")

    print()
    print("==> clientConfig.caBundle")
    print("Include this in your webhook configuration files")
    print()

    with open(Path(directory) / "ca.crt", "rb") as f:
        ca_cert = f.read()
        print(base64.b64encode(ca_cert).decode("ascii"))

    print()
    print("==> Command to create secret")
    print("Run this to upload the key material to a Kubernetes secret")
    print()

    print(
        "kubectl --namespace={0} create secret tls {1}-certs --cert={2}/server.crt --key={2}/server.key".format(
            namespace, service, directory
        )
    )
generate_keys("webhook","kube-system")