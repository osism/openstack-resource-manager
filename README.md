# openstack-resource-manager

[![Build Status](https://travis-ci.org/betacloud/openstack-resource-manager.svg?branch=master)](https://travis-ci.org/betacloud/openstack-resource-manager)

With this script it is possible to easily list orphaned resources
on an OpenStack cloud environment.

## Usage

```
$ pipenv install
$ pipenv shell
$ python src/list.py
```

```
$ docker-compose up --build list
```

## Sample output

```
neutron - rbacpolicy: 325ed31d-f72e-4d50-a889-cc8c3e7e7cc2 (project: de8299637be6486f9dd0d51c1f544a71)
neutron - rbacpolicy: 5f770027-2543-4975-8b5f-305935a1c3f3 (project: de8299637be6486f9dd0d51c1f544a71)
neutron - rbacpolicy: 605a1390-4848-45ca-96aa-efd3fa82c2a5 (project: de8299637be6486f9dd0d51c1f544a71)
neutron - rbacpolicy: 626a5a8b-2f0e-4e25-95b1-72cde4eccf45 (project: de8299637be6486f9dd0d51c1f544a71)
neutron - rbacpolicy: 74405dac-73fe-49af-afdc-094d78ad85ec (project: de8299637be6486f9dd0d51c1f544a71)
neutron - rbacpolicy: 7939a913-70e9-44af-9635-03641393b664 (project: de8299637be6486f9dd0d51c1f544a71)
neutron - rbacpolicy: b081a3a2-d4ad-428c-8c7a-e3a593e9baba (project: de8299637be6486f9dd0d51c1f544a71)
neutron - rbacpolicy: f3b37cda-6a8b-4ac4-bbe0-02a3bb5a8eab (project: de8299637be6486f9dd0d51c1f544a71)
neutron - securitygroup: 060e7e5b-c556-46f3-ba93-51e8a24dc96b (project: f1d710e89ec24e3f8356a66d3b52465b)
neutron - securitygroup: 0677f688-af65-4001-b4a0-07f5002c382c (project: d747d2e1b7f547c48a4b2b8bba85305f)
neutron - securitygroup: 1161f267-384f-4e42-855b-4093c014cd49 (project: 6c1e40626cd44340a8094d4e23c9260b)
[...]
```

## License

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
