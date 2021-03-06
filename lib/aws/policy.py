
import json
import re
from functools import reduce

from lib.aws.actions import ACTIONS
from lib.aws.resources import RESOURCES

from lib.graph.base import Element, Elements
from lib.graph.edges import Action, Trusts
from lib.graph.nodes import Resource, External


''' Consists of Principals, Actions, Resources, and Conditions '''


class Statement:

    def __init__(self, statement: dict, resource: Element, resources: Elements):

        # TODO: policy statements do not appear to strictly adhere to the JSON
        # format and may include duplicate keys. Duplicate keys will be ignored.

        self._resources = resources
        self._statement = statement
        self._resource = resource

        self._explicit_principals = None
        self._explicit_actions = None
        self._explicit_resources = None
        self._explicit_conditions = None
        self._explicit_resource_conditions = {}
        self._Actions = None

        try:

            if not isinstance(statement, dict):

                raise ValueError

            self._statement = statement

            keys = [k.replace("Not", "")
                    for k in self._statement.keys()]

            if not all([k in keys for k in ["Effect", "Action"]]):
                raise ValueError("Malformed statement: Missing 'Effect'")

            if "Resource" not in keys and resource is not None:
                self._statement["Resource"] = str(self._resource)
                self._explicit_resources = Elements([self._resource])
                self._explicit_resource_conditions = {
                    self._resource.id(): [{}]}

            elif "Resource" is None:
                raise ValueError("Malformed statement: Missing 'Resource'")

            if "Condition" not in keys:
                self._explicit_conditions = {}
            else:
                self._explicit_conditions = self._statement["Condition"]

            # TODO: Not implemented
            if "NotPrincipal" in keys:
                print("[!] 'NotPrincipal' support has not yet been added. "
                      "\n\tThis entire statement will be ingnored (%s)." % self._resource.id())
                self._explicit_principals = []

            elif "Principal" not in keys:
                self._explicit_principals = [self._resource]

        except:
            raise ValueError("Malformed statement: %s" % self._statement)

    '''https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_principal.html'''

    def _resolve_principal_statement(self):

        principals = Elements()

        key = list(filter(lambda x: "Principal" in x,
                          self._statement.keys()))[0]

        statement = self._statement[key]

        if isinstance(statement, str) and statement == "*":
            statement = {"AWS": "*"}

        if not isinstance(statement, dict):
            raise ValueError

        if "AWS" in statement:

            if not isinstance(statement["AWS"], list):
                statement["AWS"] = [statement["AWS"]]

            if '*' in statement["AWS"]:

                principals = self._resources.get(
                    'AWS::Iam::User').get("Resource") + self._resources.get(
                    'AWS::Iam::Role').get("Resource") + [External(
                        key="Arn",
                        labels=["AWS::Account"],
                        properties={
                            "Name": "All AWS Accounts",
                            "Arn": "arn:aws:iam::{Account}:root"
                        })]

            for principal in [p for p in statement["AWS"] if '*' not in statement["AWS"]]:

                if '*' in principal:
                    continue

                node = next((a for a in self._resources
                             if a.id() == principal), None)

                # We haven't seen this node before. It may belong to another account,
                # or it belongs to a service that was not loaded.

                if node is None:

                    name = principal
                    labels = []

                    if re.compile(
                        "^%s$" % RESOURCES.regex["Account"]
                    ).match(principal) is not None:

                        labels += ["AWS::Account"]
                        principal = "arn:aws:iam::{Account}:root".format(
                            Account=principal)

                    elif re.compile(
                        "^%s$" % "arn:aws:iam::{Account}:root".format(
                            Account=RESOURCES.regex["Account"])
                    ).match(principal) is not None:

                        name = str(principal.split(":")[4])
                        labels += ["AWS::Account"]

                    else:

                        for k, v in RESOURCES.items():
                            if re.compile(v).match(principal):
                                name = principal.replace(
                                    '/', ':').split(':')[-1]
                                labels = [k]
                                break

                    node = External(
                        key="Arn",
                        labels=labels,
                        properties={
                            "Name": str(name),
                            "Arn":  principal
                        })

                principals.append(node)

        elif "Service" in statement:

            pass
            # services = statement["Service"] if isinstance(
            #     statement["Service"], list) else [statement["Service"]]

            # for service in services:

            #     if service.endswith("amazonaws.com"):
            #         labels = ["AWS::Domain"]
            #     else:
            #         labels = ["Internet::Domain"]

            #     principals.append(External(
            #         labels=labels,
            #         properties={
            #             "Name": service
            #         }))

        elif "Federated" in statement:

            node = None
            labels = []

            if re.compile(
                RESOURCES["AWS::Iam::SamlProvider"]
            ).match(statement["Federated"]) is not None:

                base = Resource if (next((a for a in self._resources if a.id().split(
                    ':')[4] == statement["Federated"].split(':')[4]), False)) else External

                node = base(
                    key="Arn",
                    labels=["AWS::Iam::SamlProvider"],
                    properties={
                        "Name": statement["Federated"].split('/')[-1],
                        "Arn":  statement["Federated"]
                    })

            elif re.compile(
                "^(?=.{1,253}\.?$)(?:(?!-|[^.]+_)[A-Za-z0-9-_]{1,63}(?<!-)(?:\.|$)){2,}$"
            ).match(statement["Federated"]):

                node = External(
                    labels=["Internet::Domain"],
                    properties={
                        "Name": statement["Federated"]
                    })

            else:
                node = External(
                    properties={
                        "Name": statement["Federated"],
                    })

            principals.append(node)

        # TODO:
        elif "CanonicalUser" in statement:

            principals.append(External(
                labels=["AWS::Account"],
                properties={
                    "Name": statement["CanonicalUser"],
                    "CanonicalUser": statement["CanonicalUser"],
                    "Arn": ""
                }))

        else:
            print("Unknown pricipal: ", statement)

        self._explicit_principals = principals

    def _resolve_action_statement(self):

        actions = set()
        key = list(filter(lambda x: "Action" in x,
                          self._statement.keys()))[0]
        statement = self._statement[key] \
            if isinstance(self._statement[key], list) \
            else [self._statement[key]]

        for action in [a for a in statement if '*' not in statement]:

            if '*' in action:

                actions.update(set(filter(re.compile(
                    action.replace("*", "(.*)")).match,
                    ACTIONS.keys())))
            else:
                actions.update([action] if action in ACTIONS.keys() else [])

        if '*' in statement and key != 'NotAction':
            actions = set(ACTIONS.keys())

        elif '*' in statement:
            actions = set()

        elif key == "NotAction":

            actions = [action for action in ACTIONS
                       if action not in actions]

        self._explicit_actions = sorted(list(actions))

    def _resolve_resource_statement(self):

        resources = Elements()
        conditions = {}

        key = list(filter(lambda x: "Resource" in x,
                          self._statement.keys()))[0]
        statement = self._statement[key] \
            if isinstance(self._statement[key], list) \
            else [self._statement[key]]

        for resource in set([r.replace('*', "(.*)") + "$" for r in statement
                             if '*' not in statement
                             and len(self._resources) > 0]):

            # Identify variable resource-level permissions
            variables = list(re.findall("\$\{[0-9a-zA-Z:]+\}", resource))
            regex = re.compile(reduce(lambda x, y: x.replace(y, "(.*)"),
                                      variables,
                                      resource))

            # Match resource-level permissions against resource arns
            results = Elements(filter(lambda r: regex.match(r.id()),
                                      self._resources))

            # Standard case: add results to result set
            if len(variables) == 0:
                for r in results:
                    conditions[r.id()] = [{}]
                    if r not in resources:
                        resources.append(r)
                continue

            offset = len([x for x in resource if x == '(']) + 1

            # Handle resource-level permissions
            for result in [r for r in results
                           if r.id() not in conditions
                           or conditions[r.id()] != [{}]]:

                # TODO: skip resources that incorporate contradictory conditions
                condition = {
                    "StringEquals": {
                        variables[i]: regex.match(
                            result.id()).group(offset + i)
                        for i in range(len(variables))}
                }

                if result.id() not in conditions:
                    conditions[result.id()] = []

                if condition not in conditions[result.id()]:
                    conditions[result.id()].append(condition)

                if result not in resources:
                    resources.append(result)

        if '*' in statement:

            resources = self._resources

        elif key == "NotResource":
            resources = [r for r in self._resources
                         if r not in resources]

        self._explicit_resource_conditions = {
            r.id(): conditions[r.id()]
            if r.id() in conditions
            else [{}]
            for r in resources
        }

        self._explicit_resources = Elements(sorted(resources))

    def __str__(self):
        return str(self._statement)

    def principals(self):

        if self._explicit_principals is None:
            self._resolve_principal_statement()
        return self._explicit_principals

    def actions(self):

        if self._explicit_actions is None:
            self._resolve_action_statement()

        return self._explicit_actions

    def resources(self):

        if self._explicit_resources is None:
            self._resolve_resource_statement()

        return [str(r) for r in self._explicit_resources]

    def resolve(self):

        if self._Actions is not None:
            return self._Actions

        if self._explicit_actions is None:
            self._resolve_action_statement()
        if self._explicit_resources is None:
            self._resolve_resource_statement()
        if self._explicit_principals is None:
            self._resolve_principal_statement()

        actions = Elements()

        for action in self.actions():

            # Rewrite
            resources = Elements()
            for affected in ACTIONS[action]["Affects"]:

                resources.extend(Elements(
                    [r for r in self._explicit_resources.get(affected)
                     if r not in resources]))

            for resource in resources:

                # Action conditions comprise of resource level permission conditions
                # variants AND statement conditions

                condition = self._explicit_resource_conditions[resource.id()]

                condition = [
                    {**condition[i], **self._explicit_conditions}
                    for i in range(len(condition))]

                condition = json.dumps(condition) \
                    if len(condition[0]) > 0 else "[]"

                for principal in self._explicit_principals:
                    actions.append(Action(
                        properties={
                            "Name":         action,
                            "Description":  ACTIONS[action]["Description"],
                            "Effect":       self._statement["Effect"],
                            "Access":       ACTIONS[action]["Access"],
                            "Reference":    ACTIONS[action]["Reference"],
                            "Condition":    condition
                        },
                        source=principal, target=resource))

        # Unset resource level permission conditions
        for resource in self._explicit_resources:
            resource.condition = []

        self._Actions = actions

        return self._Actions


''' Consists of one or more Statements '''


class Document:

    def __init__(self, document, resource, resources):

        self.document = {}
        self.statements = []

        if not (isinstance(document, dict)
                and "Version" in document
                and document["Version"] == "2012-10-17"
                and "Statement" in document):
            return

        self.resource = resource
        self.document = document

        # TODO: We're going to end up with things that weren't here before
        self._document = json.dumps(
            self.document,
            indent=2,
            default=str)

        if not isinstance(document["Statement"], list):
            document["Statement"] = [document["Statement"]]

        for statement in self.document["Statement"]:
            self.statements.append(Statement(
                statement=statement,
                resource=self.resource,
                resources=resources))

    def __str__(self):
        return self._document

    def __len__(self):
        return len(self.statements)

    def principals(self):
        principals = Elements()
        for i in range(len(self.statements)):
            principals.extend([p for p in self.statements[i].principals()
                               if p not in principals])
        return principals

    def resolve(self):
        actions = Elements()
        for i in range(len(self.statements)):
            results = self.statements[i].resolve()
            # [r.set("Statement", i) for r in results]
            actions.extend(r for r in results if r not in actions)
        return actions


''' Consists of one or more Documents '''


class Policy:

    def __init__(self, resource, resources):

        self.documents = {}
        self.resource = resource
        self.resources = resources

    def __str__(self):

        return json.dumps({
            k: json.loads(str(v))
            for k, v in self.documents.items()
        }, indent=2)

    def __len__(self):
        return len(self.documents)

    def resolve(self):

        actions = Elements()
        for _, policy in self.documents.items():
            results = policy.resolve()
            # [r.set("Policy", name) for r in results]
            actions.extend([r for r in results if r not in actions])
        return actions


''' Inline and Managed Policies associated with IAM entities '''


class IdentityBasedPolicy(Policy):

    def __init__(self, resource, resources):

        super().__init__(resource, resources)
        key = list(filter(lambda k: k == "Document" or k == "Documents",
                          self.resource.properties().keys()))

        if len(key) != 1:
            return

        for policy in self.resource.properties()[key[0]]:
            for name, document in policy.items():
                self.documents[name] = Document(document, resource, resources)


''' Policies that define actions permitted to be performed on the associated resource. '''


class ResourceBasedPolicy(Policy):

    # https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_aws-services-that-work-with-iam.html

    def __init__(self, resource, resources, keys=[]):

        super().__init__(resource, resources)

        for k, v in resource.properties().items():

            if len(keys) == 0 or k in keys:
                document = Document(v, resource, resources)

                if len(document) > 0:
                    self.documents[k] = Document(
                        resource.properties()[k], resource, resources)

    def principals(self):

        principals = Elements()
        for _, policy in self.documents.items():
            results = policy.principals()
            principals.extend(results)
        return principals


''' Resource based policy variant, specific to S3 Buckets and their Objects '''


class BucketACL(ResourceBasedPolicy):
    # https://docs.aws.amazon.com/AmazonS3/latest/dev/acl-overview.html#specifying-grantee

    AccessControlList = {
        "READ": [
            "s3:ListBucket",
            "s3:ListBucketVersions",
            "s3:ListBucketMultipartUploads"
        ],
        "WRITE": [
            "s3:PutObject",
            "s3:DeleteObject"
        ],
        "READ_ACP": [
            "s3:GetBucketAcl"
        ],
        "WRITE_ACP": [
            "s3:PutBucketAcl"
        ],
        "FULL_CONTROL": [
            "s3:DeleteObject",
            "s3:GetBucketAcl",
            "s3:ListBucket",
            "s3:ListBucketMultipartUploads",
            "s3:ListBucketVersions",
            "s3:PutBucketAcl",
            "s3:PutObject"
        ],
    }

    def __init__(self, resource, resources):

        statements = []

        for key, acls in resource.properties().items():

            # Property is not a valid ACL

            if not (isinstance(acls, list)
                    and all(["Grantee" in x and "Permission" for x in acls])):
                continue

            # Construct a policy from ACL

            for (grantee, permission) in map(lambda x: (x["Grantee"], x["Permission"]), acls):

                statement = {
                    "Effect": "Allow"
                }

                # Handle Principal

                if grantee["Type"] not in ["CanonicalUser", "Group"]:
                    raise ValueError

                if grantee["Type"] == "CanonicalUser":

                    statement["Principal"] = {"CanonicalUser": grantee["ID"]}

                elif grantee["Type"] == "Group":

                    group = grantee["URI"].split('/')[-1]

                    # Any AWS account can access this resource

                    if group == "AuthenticatedUsers":
                        statement["Principal"] = {"AWS": "*"}

                    # Anyone (not neccessarily AWS)

                    elif group == "AllUsers":
                        statement["Principal"] = {"AWS": "*"}

                    # Service

                    elif group == "LogDelivery":
                        statement["Principal"] = {"Service": grantee["URI"]}

                    # Specific AWS resource

                    else:
                        statement["Principal"] = {"AWS": grantee["URI"]}

                # Handle Actions

                statement["Action"] = self.AccessControlList[permission]

                # Handle Resources (Bucket and Objects in Bucket)

                statement["Resource"] = [resource.id(), resource.id() + "/*"]

                statements.append(statement)

        if len(statements) > 0:

            resource.properties()["_"] = {
                "Version": "2012-10-17",
                "Statement": statements
            }

        super().__init__(resource, resources, keys=["_"])

        if "_" in resource.properties():
            del resource.properties()["_"]
