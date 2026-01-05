CONFIG = {
    "i2edge": {
        "ZONE_ID": "f0662bfe-1d90-5f59-a759-c755b3b69b93",
        "APP_ONBOARD_MANIFEST_GSMA": {
            "appId": "demo-app-id",
            "appProviderId": "Y89TSlxMPDKlXZz7rN6vU2y",
            "appDeploymentZones": [
                "Dmgoc-y2zv97lar0UKqQd53aS6MCTTdoGMY193yvRBYgI07zOAIktN2b9QB2THbl5Gqvbj5Zp92vmNeg7v4M"
            ],
            "appMetaData": {
                "appName": "pj1iEkprop",
                "version": "string",
                "appDescription": "stringstringstri",
                "mobilitySupport": False,
                "accessToken": "MfxADOjxDgBhMrqmBeG8XdQFLp2XviG3cZ_LM7uQKc9b",
                "category": "IOT",
            },
            "appQoSProfile": {
                "latencyConstraints": "NONE",
                "bandwidthRequired": 1,
                "multiUserClients": "APP_TYPE_SINGLE_USER",
                "noOfUsersPerAppInst": 1,
                "appProvisioning": True,
            },
            "appComponentSpecs": [
                {
                    "serviceNameNB": "k8yyElSyJN4ctbNVqwodEQNUoGb2EzOEt4vQBjGnPii_5",
                    "serviceNameEW": "iDm08OZN",
                    "componentName": "HIEWqstajCmZJQmSFUj0kNHZ0xYvKWq720BKt8wjA41p",
                    "artefactId": "i2edgechart",
                }
            ],
            "appStatusCallbackLink": "string",
            "edgeAppFQDN": "string",
        },
        "APP_DEPLOY_PAYLOAD_GSMA": {
            "appId": "demo-app-id",
            "appVersion": "string",
            "appProviderId": "Y89TSlxMPDKlXZz7rN6vU2y",
            "zoneInfo": {
                "zoneId": "f0662bfe-1d90-5f59-a759-c755b3b69b93",
                "flavourId": "6881e358535a2eaedcb27214",
                "resourceConsumption": "RESERVED_RES_AVOID",
                "resPool": "ySIT0LuZ6ApHs0wlyGZve",
            },
            "appInstCallbackLink": "string",
        },
        "PATCH_ONBOARDED_APP_GSMA": {
            "appUpdQoSProfile": {
                "latencyConstraints": "NONE",
                "bandwidthRequired": 1,
                "mobilitySupport": False,
                "multiUserClients": "APP_TYPE_SINGLE_USER",
                "noOfUsersPerAppInst": 1,
                "appProvisioning": True,
            },
            "appComponentSpecs": [
                {
                    "serviceNameNB": "7CI_9d4lAK90vU4ASUkKxYdQjsv3y3IuwucISSQ6lG5_EMqeyVUHPIhwa5",
                    "serviceNameEW": "tPihoUFj30938Bu9blpsHkvsec1iA7gqZZRMpsx6o7aSSj5",
                    "componentName": "YCAhqPadfld8y68wJfTc6QNGguI41z",
                    "artefactId": "i2edgechart",
                },
                {
                    "serviceNameNB": "JCjR0Lc3J0sm2PcItECdbHXtpCLQCfq3B",
                    "serviceNameEW": "N8KBAdqT8L_sWOxeFZs3XYn6oykTTFHLiPKOS7kdYbw",
                    "componentName": "9aCfCEDe2Dv0Peg",
                    "artefactId": "i2edgechart",
                },
                {
                    "serviceNameNB": "RIfXlfU9cDeLnrOBYzz9LJGdAjwPRp_3Mjp0Wq_RDlQiAPyXm",
                    "serviceNameEW": "31y8sCwvvyNCXfwtLhwJw6hoblG7ZcFzEjyFdAnzq7M8cxiOtDik0",
                    "componentName": "3kTa4zKEX",
                    "artefactId": "i2edgechart",
                },
            ],
        },
        "ARTEFACT_GSMA": {
            "artefactId": "i2edgechart",
            "appProviderId": "string",
            "artefactName": "i2edgechart",
            "artefactVersionInfo": "string",
            "artefactDescription": "string",
            "artefactVirtType": "VM_TYPE",
            "artefactFileName": "string",
            "artefactFileFormat": "ZIP",
            "artefactDescriptorType": "HELM",
            "repoType": "PUBLICREPO",
            "artefactRepoLocation": {
                "repoURL": "https://cesarcajas.github.io/helm-charts-examples/",
                "userName": "string",
                "password": "string",
                "token": "string",
            },
            "artefactFile": "string",
            "componentSpec": [
                {
                    "componentName": "string",
                    "images": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
                    "numOfInstances": 0,
                    "restartPolicy": "RESTART_POLICY_ALWAYS",
                    "commandLineParams": {"command": ["string"], "commandArgs": ["string"]},
                    "exposedInterfaces": [
                        {
                            "interfaceId": "string",
                            "commProtocol": "TCP",
                            "commPort": 0,
                            "visibilityType": "VISIBILITY_EXTERNAL",
                            "network": "string",
                            "InterfaceName": "string",
                        }
                    ],
                    "computeResourceProfile": {
                        "cpuArchType": "ISA_X86_64",
                        "numCPU": {
                            "whole": {"value": 2},
                            "decimal": {"value": 0.5},
                            "millivcpu": {"value": "500m"},
                        },
                        "memory": 0,
                        "diskStorage": 0,
                        "gpu": [
                            {
                                "gpuVendorType": "GPU_PROVIDER_NVIDIA",
                                "gpuModeName": "string",
                                "gpuMemory": 0,
                                "numGPU": 0,
                            }
                        ],
                        "vpu": 0,
                        "fpga": 0,
                        "hugepages": [{"pageSize": "2MB", "number": 0}],
                        "cpuExclusivity": True,
                    },
                    "compEnvParams": [
                        {
                            "envVarName": "string",
                            "envValueType": "USER_DEFINED",
                            "envVarValue": "string",
                            "envVarSrc": "string",
                        }
                    ],
                    "deploymentConfig": {
                        "configType": "DOCKER_COMPOSE",
                        "contents": "string",
                    },
                    "persistentVolumes": [
                        {
                            "volumeSize": "10Gi",
                            "volumeMountPath": "string",
                            "volumeName": "string",
                            "ephemeralType": False,
                            "accessMode": "RW",
                            "sharingPolicy": "EXCLUSIVE",
                        }
                    ],
                }
            ],
        },
    },
    "aeros": {
        "ZONE_ID": "urn:ngsi-ld:Domain:ncsrd01",
        "ARTEFACT_ID": "artefact-nginx-001",
        "ARTEFACT_NAME": "aeros-component",
        "REPO_NAME": "dockerhub",
        "REPO_TYPE": "PUBLICREPO",
        "REPO_URL": "docker.io/library/nginx:stable",
        "APP_ONBOARD_MANIFEST_GSMA": {
            "appId": "aeros-sdk-app",
            "appProviderId": "aeros-sdk-provider",
            "appDeploymentZones": ["urn:ngsi-ld:Domain:ncsrd01"],
            "appMetaData": {
                "appName": "aeros_SDK_app",
                "version": "string",
                "appDescription": "test aeros sdk app",
                "mobilitySupport": False,
                "accessToken": "MfxADOjxDgBhMrqmBeG8XdQFLp2XviG3cZ_LM7uQKc9b",
                "category": "IOT",
            },
            "appQoSProfile": {
                "latencyConstraints": "NONE",
                "bandwidthRequired": 1,
                "multiUserClients": "APP_TYPE_SINGLE_USER",
                "noOfUsersPerAppInst": 1,
                "appProvisioning": True,
            },
            "appComponentSpecs": [
                {
                    "serviceNameNB": "gsma-deployed-app-service-nb",
                    "serviceNameEW": "gsma-deployed-app-service-ew",
                    "componentName": "nginx-component",
                    "artefactId": "artefact-nginx-001",
                }
            ],
            "appStatusCallbackLink": "string",
            "edgeAppFQDN": "string",
        },
        "APP_DEPLOY_PAYLOAD_GSMA": {
            "appId": "aeros-sdk-app",
            "appVersion": "1.0.0",
            "appProviderId": "apps-sdk-deployer",
            "zoneInfo": {
                "zoneId": "urn:ngsi-ld:Domain:ncsrd01",
                "flavourId": "FLAVOUR_BASIC",
                "resourceConsumption": "RESERVED_RES_AVOID",
                "resPool": "RESPOOL_DEFAULT",
            },
            "appInstCallbackLink": "string",
        },
        "PATCH_ONBOARDED_APP_GSMA": {
            "appUpdQoSProfile": {
                "latencyConstraints": "NONE",
                "bandwidthRequired": 1,
                "mobilitySupport": False,
                "multiUserClients": "APP_TYPE_SINGLE_USER",
                "noOfUsersPerAppInst": 1,
                "appProvisioning": True,
            },
            "appComponentSpecs": [
                {
                    "serviceNameNB": "gsma-deployed-app-service-nb",
                    "serviceNameEW": "gsma-deployed-app-service-ew",
                    "componentName": "nginx-component",
                    "artefactId": "artefact-nginx-001",
                },
                {
                    "serviceNameNB": "JCjR0Lc3J0sm2PcItECdbHXtpCLQCfq3B",
                    "serviceNameEW": "N8KBAdqT8L_sWOxeFZs3XYn6oykTTFHLiPKOS7kdYbw",
                    "componentName": "9aCfCEDe2Dv0Peg",
                    "artefactId": "9c9143f0-f44f-49df-939e-1e8b891ba8f5",
                },
                {
                    "serviceNameNB": "RIfXlfU9cDeLnrOBYzz9LJGdAjwPRp_3Mjp0Wq_RDlQiAPyXm",
                    "serviceNameEW": "31y8sCwvvyNCXfwtLhwJw6hoblG7ZcFzEjyFdAnzq7M8cxiOtDik0",
                    "componentName": "3kTa4zKEX",
                    "artefactId": "9c9143f0-f44f-49df-939e-1e8b891ba8f5",
                },
            ],
        },
        "ARTEFACT_PAYLOAD_GSMA": {
            "artefactId": "artefact-nginx-001",
            "appProviderId": "ncsrd-provider",
            "artefactName": "nginx-web-server",
            "artefactVersionInfo": "1.0.0",
            "artefactDescription": "Containerized Nginx Web Server",
            "artefactVirtType": "CONTAINER_TYPE",
            "artefactFileName": "nginx-web-server-1.0.0.tgz",
            "artefactFileFormat": "TARGZ",
            "artefactDescriptorType": "COMPONENTSPEC",
            "repoType": "PUBLICREPO",
            "artefactRepoLocation": {
                "repoURL": "docker.io/library/nginx:stable",
                "userName": "",
                "password": "",
                "token": "",
            },
            "artefactFile": "",
            "componentSpec": [
                {
                    "componentName": "nginx-component",
                    "images": ["docker.io/library/nginx:stable"],
                    "numOfInstances": 1,
                    "restartPolicy": "Always",
                    "commandLineParams": {},
                    "exposedInterfaces": [{"name": "http-api", "protocol": "TCP", "port": 8080}],
                    "computeResourceProfile": {"cpu": "2", "memory": "4Gi"},
                    "compEnvParams": [{"name": "TEST_ENV", "value": "TEST_VALUE_ENV"}],
                    "deploymentConfig": {"replicaStrategy": "RollingUpdate", "maxUnavailable": 1},
                    "persistentVolumes": [
                        {"name": "NOT_USE", "mountPath": "NOT_USED", "size": "NOT_USED"}
                    ],
                }
            ],
        },
    },
    "kubernetes": {
        # PLACEHOLDER
    },
}
