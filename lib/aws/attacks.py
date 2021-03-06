#!/usr/bin/python3

import copy
import json
import re

from lib.graph.db import Neo4j


class Attacks:

    definitions = {

        "CreatePolicyVersion": {

            "Description": "Overwrite the default version of the "
            "target managed policy:",

            "Options": ["Admin"],

            "Commands": [
                "aws create-policy-version "
                "--policy-arn ${AWS::Iam::Policy}.Arn "
                "--set-as-default "
                "--policy-document file://<(cat <<EOF\n"
                "{\n"
                "    \"Version\": \"2012-10-17\",\n"
                "    \"Statement\": [\n"
                "        {\n"
                "            \"Sid\": \"Admin\",\n"
                "            \"Effect\": \"Allow\",\n"
                "            \"Action\": \"*\",\n"
                "            \"Resource\": \"*\"\n"
                "        }]\n"
                "}\n"
                "EOF\n"
                ")"

            ],

            "Attack": {

                "Depends": "AWS::Iam::Policy",

                "Requires": [
                    "iam:CreatePolicyVersion"
                ],

                "Affects": "AWS::Iam::Policy",

                # "Cypher": [
                #     "(SIZE(SPLIT("
                #     "${AWS::Iam::Policy}.PolicyVersionList,"
                #     "'IsDefaultVersion')) - 1) < 5"
                # ],

            },

            "Grants": "Admin"
        },

        "AssociateInstanceProfile": {

            "Description": "Associate the specified instance with "
            "the target instance profile: ",

            "Commands": [
                "aws ec2 associate-iam-instance-profile "
                "--iam-instance-profile Name=${AWS::Iam::InstanceProfile} "
                "--instance-id ${AWS::Ec2::Instance}"
            ],

            "Attack": {

                "Depends": "AWS::Ec2::Instance",

                "Requires": [
                    "ec2:AssociateIamInstanceProfile"
                ],

                "Affects": "AWS::Ec2::Instance",

                "Grants": "AWS::Iam::InstanceProfile",

                "Cypher": [
                    "(${AWS::Iam::InstanceProfile})-[{Name:'Attached'}]->(${AWS::Iam::Role})",
                    "(${})-[:TRANSITIVE*..]->()-[{Name:'iam:PassRole'}]->(${AWS::Iam::Role})"
                ],

            },

            "Grants": "Attached",
        },

        "AssumeRole": {

            "Description": "Retrieve a set of temporary security credentials "
            "by assuming the target role:",

            "Commands": [
                "aws sts assume-role "
                "--role-arn ${AWS::Iam::Role}.Arn "
                "--role-session-name AssumeRole"
            ],

            "Attack": {

                "Requires": [
                    "sts:AssumeRole"
                ],

                "Affects": "AWS::Iam::Role",

                "Cypher": [
                    "(${})<-[:TRUSTS{Name:'sts:AssumeRole'}]-(${AWS::Iam::Role})"
                ],

            },

            "Grants": "AssumeRole",
        },

        #  TODO: Producing false positives, requires further testing.
        # "AddRoleToInstanceProfile": {

        #     "Description": "Add the target role to "
        #     "the specified instance profile:",

        #     "Commands": [
        #         "aws iam add-role-to-instance-profile"
        #         "--instance-profile-name ${AWS::Iam::InstanceProfile} "
        #         "--role-name ${AWS::Iam::Role}"],

        #     "Attack": {

        #         "Depends": "AWS::Iam::InstanceProfile",

        #         "Requires": [
        #             "iam:AddRoleToInstanceProfile"
        #         ],

        #         "Affects": "AWS::Iam::InstanceProfile",

        #         "Grants": "AWS::Iam::Role",

        #     },

        #     "Grants": "Attached",
        # },

        "AddUserToGroup": {

            "Description": "Add the specified user to the target group:",

            "Commands": [
                "aws iam add-user-to-group "
                "--user-name ${AWS::Iam::User} "
                "--group-name ${AWS::Iam::Group}"
            ],

            "Attack": {

                "Depends": "AWS::Iam::User",

                "Requires": [
                    "iam:AddUserToGroup"
                ],

                "Affects": "AWS::Iam::Group",

            },

            "Grants": "MemberOf"
        },

        "AttachGroupPolicy": {

            "Description": "Attach the target managed "
            "policy to the specified group:",

            "Commands": [
                "aws iam attach-group-policy "
                "--group-name ${AWS::Iam::Group} "
                "--policy-arn ${AWS::Iam::Policy}.Arn",
            ],

            "Attack": {

                "Depends": "AWS::Iam::Group",

                "Requires": [
                    "iam:AttachGroupPolicy",
                ],

                "Affects": "AWS::Iam::Group",

                "Grants": "AWS::Iam::Policy"

            },

            "Grants": "Attached"
        },

        "AttachRolePolicy": {

            "Description": "Attach the target managed "
            "policy to the specified role:",

            "Commands": [
                "aws iam attach-role-policy "
                "--role-name ${AWS::Iam::Role} "
                "--policy-arn ${AWS::Iam::Policy}.Arn"
            ],

            "Attack": {

                "Depends": "AWS::Iam::Role",

                "Requires": [
                    "iam:AttachRolePolicy"
                ],

                "Affects": "AWS::Iam::Role",

                "Grants": "AWS::Iam::Policy"
            },

            "Grants": "Attached"
        },

        "AttachUserPolicy": {

            "Description": "Attach the target managed "
            "policy to the specified user.",

            "Commands": [
                "aws iam attach-user-policy "
                "--user-name ${AWS::Iam::User} "
                "--policy-arn ${AWS::Iam::Policy}.Arn",
            ],

            "Attack": {

                "Depends": "AWS::Iam::User",

                "Requires": [
                    "iam:AttachUserPolicy",
                ],

                "Affects": "AWS::Iam::User",

                "Grants": "AWS::Iam::Policy",

            },

            "Grants": "Attached"
        },

        "CreateGroup": {

            "Description": "Create a new group and add the specified user to it:",

            "Options": ["CreateAction"],

            "Commands": [
                "aws iam create-group --group-name ${AWS::Iam::Group}",

                "aws iam add-user-to-group "
                "--user-name ${AWS::Iam::User} "
                "--group-name ${AWS::Iam::Group}"
            ],

            "Attack": {

                "Depends": "AWS::Iam::User",

                "Requires": [
                    "iam:CreateGroup",
                    "iam:AddUserToGroup",
                ],

                "Affects": "AWS::Iam::Group"

            },
        },

        "CreateInstance": {

            "Description": "Launch a new Ec2 instance:",

            "Options": ["CreateAction"],

            "Commands": [
                "aws ec2 run-instances "
                "--count 1 "
                "--instance-type t2.micro"
                "--image-id $ami-id",
            ],

            "Attack": {

                "Requires": [
                    "ec2:RunInstances"
                ],

                "Affects": "AWS::Ec2::Instance",

            }
        },

        "CreateInstanceProfile": {

            "Description": "Create a new instance profile",

            "Options": ["CreateAction"],

            "Commands": [
                "aws iam create-instance-profile "
                "--instance-profile-name ${AWS::Iam::InstanceProfile}"
            ],


            "Attack": {

                "Requires": [
                    "iam:CreateInstanceProfile"
                ],

                "Affects": "AWS::Iam::InstanceProfile",

            }
        },

        "CreatePolicy": {

            "Description": "Create a new managed policy:",

            "Options": ["CreateAction"],

            "Commands": [
                "aws iam create-policy "
                "--policy-name $policy-name "
                "--policy-document file://<(cat <<EOF\n"
                "{\n"
                "    \"Version\": \"2012-10-17\",\n"
                "    \"Statement\": [\n"
                "        {\n"
                "            \"Sid\": \"Admin\",\n"
                "            \"Effect\": \"Allow\",\n"
                "            \"Action\": \"*\",\n"
                "            \"Resource\": \"*\"\n"
                "        }]\n"
                "}\n"
                "EOF\n"
                ")"
            ],

            "Attack": {

                "Requires": [
                    "iam:CreatePolicy",
                ],

                "Affects": "AWS::Iam::Policy",

            },
        },

        "CreateRole": {

            "Description": "Create a new role:",

            "Options": ["CreateAction"],

            "Commands": [
                "aws iam create-role --role-name ${AWS::Iam::Role} "
                "--assume-role-policy-document *",
            ],

            "Attack": {

                "Requires": [
                    "iam:CreateRole",
                ],

                "Affects": "AWS::Iam::Role",

            },

            "Grants": "AssumeRole"
        },

        # "CreateSnapshot": {

        #     "Description": "Create a snapshot of the target volume "
        #     "and gain read access to it by launching a new Ec2 instance that mounts it:",

        #     "Commands": [
        #         "aws ec2 create-snapshot ${AWS::Ec2::Volume}",
        #         "aws ec2 run-instances "
        #         "--block-device-mapping \"DeviceName=/dev/sda2,Ebs={SnapshotId=${AWS::Ec2::Volume}}\""
        #     ],

        #     "Attack": {

        #         "Requires": [
        #             "ec2:CreateSnapshot",
        #             "ec2:RunInstances"
        #         ],

        #         "Affects": "AWS::Ec2::Volume",

        #     },

        #     "Grants": "ReadFileSystem"
        # },

        "CreateUserLoginProfile": {

            "Description": "Create a new user:",

            "Options": ["CreateAction"],

            "Commands": [
                "aws iam create-user --user-name ${AWS::Iam::User}",
                "aws iam create-login-profile --user-name ${AWS::Iam::User} "
                "--password $new-password"
            ],

            "Attack": {

                "Requires": [
                    "iam:CreateUser",
                    "iam:CreateLoginProfile"
                ],

                "Affects": "AWS::Iam::User",

            }
        },

        "PutGroupPolicy": {

            "Description": "Add a new administrative inline policy document to the target group:",

            "Options": ["Admin"],

            "Commands": [
                "aws iam put-group-policy --group-name ${AWS::Iam::Group} "
                "--policy-name Admin "
                "--policy-document file://<(cat <<EOF\n"
                "{\n"
                "    \"Version\": \"2012-10-17\",\n"
                "    \"Statement\": [\n"
                "        {\n"
                "            \"Sid\": \"Admin\",\n"
                "            \"Effect\": \"Allow\",\n"
                "            \"Action\": \"*\",\n"
                "            \"Resource\": \"*\"\n"
                "        }]\n"
                "}\n"
                "EOF\n"
                ")"
            ],

            "Attack": {

                "Depends": "AWS::Iam::Group",

                "Requires": [
                    "iam:PutGroupPolicy"
                ],

                "Affects": "AWS::Iam::Group"

            },
        },

        "PutRolePolicy": {

            "Description": "Add a new administrative inline policy document to the target role:",

            "Options": ["Admin"],

            "Commands": [
                "aws iam put-role-policy --role-name ${AWS::Iam::Role} "
                "--policy-name Admin "
                "--policy-document file://<(cat <<EOF\n"
                "{\n"
                "    \"Version\": \"2012-10-17\",\n"
                "    \"Statement\": [\n"
                "        {\n"
                "            \"Sid\": \"Admin\",\n"
                "            \"Effect\": \"Allow\",\n"
                "            \"Action\": \"*\",\n"
                "            \"Resource\": \"*\"\n"
                "        }]\n"
                "}\n"
                "EOF\n"
                ")"
            ],

            "Attack": {

                "Depends": "AWS::Iam::Role",

                "Requires": [
                    "iam:PutRolePolicy"
                ],

                "Affects": "AWS::Iam::Role"

            },
        },

        "PutUserPolicy": {

            "Description": "Add a new administrative inline policy document to the target user:",

            "Options": ["Admin"],

            "Commands": [
                "aws iam put-user-policy --user-name ${AWS::Iam::User} "
                "--policy-name Admin "
                "--policy-document file://<(cat <<EOF\n"
                "{\n"
                "    \"Version\": \"2012-10-17\",\n"
                "    \"Statement\": [\n"
                "        {\n"
                "            \"Sid\": \"Admin\",\n"
                "            \"Effect\": \"Allow\",\n"
                "            \"Action\": \"*\",\n"
                "            \"Resource\": \"*\"\n"
                "        }]\n"
                "}\n"
                "EOF\n"
                ")"
            ],

            "Attack": {

                "Depends": "AWS::Iam::User",

                "Requires": [
                    "iam:PutUserPolicy"
                ],

                "Affects": "AWS::Iam::User"

            },
        },

        "UpdateRole": {

            "Description": "Update the assume-role policy document of "
            "the target role and assume it thereafter:",

            "Commands": [
                "aws iam update-assume-role-policy "
                "--role-name ${AWS::Iam::Role} "
                "--policy-document *",

                "aws sts assume-role "
                "--role-arn ${AWS::Iam::Role}.Arn "
                "--role-session-name AssumeRole"
            ],

            "Attack": {

                "Requires": [
                    "iam:UpdateAssumeRolePolicy"
                ],

                "Affects": "AWS::Iam::Role"

            },

            "Grants": "AssumeRole"
        },

        "UpdateUserLoginProfile": {

            "Description": "Reset the target user's console password and login as them:",

            "Commands": [
                "aws iam update-login-profile "
                "--user-name ${AWS::Iam::User} "
                "--password $Password "
            ],

            "Attack": {

                "Requires": [
                    "iam:UpdateLoginProfile"
                ],

                "Affects": "AWS::Iam::User"

            },

            "Grants": "ChangePassword"
        },

        "SetUserLoginProfile": {

            "Description": "Set a console password for the target user and login as them, nothing has been set before:",

            "Commands": [
                "aws iam create-login-profile "
                "--user-name ${AWS::Iam::User} "
                "--password $Password "
            ],

            "Attack": {

                "Requires": [
                    "iam:CreateLoginProfile"
                ],

                "Affects": "AWS::Iam::User",

                "Cypher": [
                    "${AWS::Iam::User}.LoginProfile IS NULL"
                ],
            },

            "Grants": "SetPassword"
        },

        "CreateUserAccessKey": {

            "Description": "Create an access key for the target user and authenticate as them using the API:",

            "Commands": [
                "aws iam create-access-key "
                "--user-name ${AWS::Iam::User} "
            ],

            "Attack": {

                "Requires": [
                    "iam:CreateAccessKey"
                ],

                "Affects": "AWS::Iam::User",

                "Cypher": [
                    "(COALESCE(SIZE(SPLIT("
                    "${AWS::Iam::User}.AccessKeys,"
                    "'Status')), 1) - 1) < 2",
                ],

            },

            "Grants": "CreateAccessKey"
        },

        "ReplaceUserAccessKey": {

            "Description": "Create, or replace, an access key for the target user and authenticate as them using the API:",

            "Commands": [
                "aws iam delete-access-key "
                "--user-name ${AWS::Iam::User} "
                "--access-key-id $AccessKeyId",
                "aws iam create-access-key "
                "--user-name ${AWS::Iam::User} "
            ],

            "Attack": {

                "Requires": [
                    "iam:DeleteAccessKey",
                    "iam:CreateAccessKey"
                ],

                "Affects": "AWS::Iam::User",

                "Cypher": [
                    "(SIZE(SPLIT("
                    "${AWS::Iam::User}.AccessKeys,"
                    "'Status')) - 1) > 0",
                ],

            },

            "Grants": "ReplaceAccessKey"
        },

    }

    @staticmethod
    def _admin_cypher():

        return (
            "MERGE (admin:Admin:`AWS::Iam::Policy`{"
            "Name: 'Effective Admin', "
            "Arn: 'arn:aws:iam::$account:policy/Admin', "
            'Document: \'[{"DefaultVersion": {"Version": "2012-10-17", '
            '"Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"'
            '}]}}]\''
            '}) '
        )

        # Replace the above with following create ACTIONs from :Admin
        # return (
        #     "MERGE (admin:Admin:`AWS::Iam::Policy) "
        #     "WITH admin "
        #     "MATCH ()-[action:ACTION]->(target:Generic) "
        #     "WHERE NOT (admin:Resource OR admin:Generic) "

        #     "WITH admin, [_ IN LABELS(target) WHERE _ =~ 'AWS::.*'][0] AS type, "
        #     "COLLECT([action.Name, action.Access, action.Description, action.Reference]) AS actions "

        #     "MATCH (resource:Resource) WHERE ANY(_ IN LABELS(resource) WHERE type = _) "

        #     "WITH admin, resource, actions "
        #     "UNWIND actions AS action "

        #     "WITH admin, resource, action[0] AS name, action[1] AS access, "
        #     "COALESCE(action[2],'') AS description, COALESCE(action[3],'') AS reference "
        #     "MERGE (admin)-[:ACTION{Name:name, Access: access, Description: description, "
        #     "Effect: 'Allow', Reference: reference}]->(resource)"
        # )

    @staticmethod
    def _pattern_cypher(
            name,
            definition,
            ignore_actions_with_conditions=True,
            max_search_depth=""):

        definition = copy.deepcopy(definition)
        attack = definition["Attack"]

        CYPHER = ""
        VARs = {
            "target_type": attack["Affects"],
            "grants_type": attack["Grants"]
            if "Grants" in attack
            else "",
            "name": name,
            "description": definition["Description"],
            "requires_list": attack["Requires"],
            "requires": attack["Requires"],
            "commands": definition["Commands"],
            "attack": name,
            "dependency": attack["Depends"]
            if "Depends" in attack
            else "",
            "grants": definition["Grants"]
            if "Grants" in definition
            else "Create",
            "depth": max_search_depth,
            "steps": len(definition["Commands"]),
            "size": len(attack["Requires"]),
        }

        OPTs = {
            "CreateAction": True if "Options" in definition
            and "CreateAction" in definition["Options"]
            else False,
            "Admin":        True if "Options" in definition
            and "Admin" in definition["Options"]
            else False,
        }

        def cypher_resolve_commands(history=False):

            # A nested REPLACE operation must occur for every placeholder in the
            # format string, each of which has to be resolved. Resolution occurs
            # by performing a type comparison against fields in the pattern's
            # definition.

            _CYPHER_ = "_"

            for (placeholder, attr) in sorted(
                re.findall(r"(\$\{AWS\:\:[A-Za-z0-9]+\:\:[A-Za-z0-9]+\})(\.[A-Za-z]+)?",
                           ';'.join(VARs["commands"])),
                key=lambda x: len(x[0]+x[1]),
                    reverse=True):

                if re.search(r'"%s", [a-z]+%s' % (placeholder, attr),
                             _CYPHER_) is not None:
                    continue

                if "${%s}" % attack["Affects"] == placeholder:
                    substitute = "grant" if "Grants" not in attack else "option"
                elif "Depends" in attack \
                        and "${%s}" % attack["Depends"] == placeholder:
                    substitute = "option"
                elif "Grants" in attack \
                        and "${%s}" % attack["Grants"] == placeholder:
                    substitute = "grant"
                # else:
                #     error("%s: %s not found" % (name, placeholder))

                if len(attr) == 0:
                    substitute += ".Name"
                else:
                    substitute += attr
                    placeholder += attr

                _CYPHER_ = "REPLACE(%s, \"%s\", %s)" \
                    % (_CYPHER_, placeholder, substitute)

            _CYPHER_ = ("EXTRACT(_ IN %s|%s)" % (VARs["commands"], _CYPHER_)
                        ).replace('{', '{{').replace('}', '}}')

            if history:

                _CYPHER_ = (
                    "REDUCE(commands=[], _ IN history + %s|"
                    "CASE WHEN _ IN commands THEN commands "
                    "ELSE commands + _ END) "
                    "AS commands") % (_CYPHER_)

            else:
                _CYPHER_ += " AS commands"

            return _CYPHER_

        def resolve_placeholder(placeholder):

            if "${}" == placeholder:
                return "source"

            elif "${%s}" % attack["Affects"] == placeholder:
                return "target"

            elif "Depends" in attack  \
                    and "${%s}" % attack["Depends"] == placeholder:
                return "option"

            elif "Grants" in attack  \
                    and "${%s}" % attack["Grants"] == placeholder:
                return "grant"

            else:
                r = re.compile(
                    "\$\{(AWS\:\:[A-Za-z0-9:]+)\}").match(placeholder)

                if r.group(1) is not None:
                    return "%s:`%s`" % (r.group(1).replace(':', '').lower(), r.group(1))

                # else:
                #     notice("subject %s malformed" % placeholder, True)

        def process_cypher():

            WITH = ["source", "edge", "options", "target", "path", "grants"]
            CONSTRAINTS = attack["Cypher"]
            UNWIND = []

            placeholders = {
                k: resolve_placeholder(k) for k in set(
                    [r for (r, _) in re.findall(
                        r"(\$\{(AWS\:\:[A-Za-z0-9]+\:\:[A-Za-z0-9]+)?\})",
                        ' '.join(attack["Cypher"]))])
            }

            for i in range(len(CONSTRAINTS)):

                for k, v in placeholders.items():
                    if v not in UNWIND \
                            and (v == "option" or v == "grant"):
                        UNWIND.append(v)
                    CONSTRAINTS[i] = CONSTRAINTS[i].replace(k, v)

                CONSTRAINTS[i] = CONSTRAINTS[i].replace(
                    "{", "{{").replace(
                    "}", "}}")

            if len(UNWIND) > 0:

                CONSTRAINTS = " ".join((
                    "WITH %s" % ", ".join(WITH),
                    "%s" % " ".join(["UNWIND %s AS %s" % (i, i[:-1])
                                     for i in WITH
                                     if i[:-1] in UNWIND]),
                    "WITH %s" % ", ".join(
                        [i if i[:-1] not in UNWIND
                         else "{i}[0] AS {i}, {i}[1] AS {i}_commands".format(i=i[:-1])
                         for i in WITH]),
                    "MATCH %s" % ', '.join(CONSTRAINTS),
                    "WITH %s" % ", ".join(
                        [i if i[:-1] not in UNWIND
                         else "COLLECT([{i},{i}_commands]) AS {j}".format(i=i[:-1], j=i)
                         for i in WITH])
                ))

            else:
                CONSTRAINTS = "AND %s" % "AND ".join(CONSTRAINTS)

            return CONSTRAINTS

        # If a node, or edge, is identified to grant Admin, it is excluded from
        # search. This is because all patterns incorporating Admin are implied
        # - searching further would be redundant.

        CYPHER += (
            "OPTIONAL MATCH (ADMIN:Resource) "
            "WHERE (ADMIN)-[:ATTACK*0..2]->(:Admin) "
            "OR (ADMIN)-[:ATTACK]->(:Pattern)-[:ATTACK{{Admin:True}}]->() "
            "OPTIONAL MATCH (admin:Resource)-[:ATTACK|TRANSITIVE*0..]->(ADMIN) "
            "WITH  REDUCE(admins=[], _ IN COLLECT(admin)|"
            "CASE WHEN _ IN admins THEN admins "
            "ELSE admins + _ END) AS admin "
            "WITH COALESCE(admin, []) AS admin, [[NULL, []]] AS options, [NULL, []] AS grants "
        )

        # Patterns including a "Depends" value require an additional argument, which must
        # be reachable. This amounts to determining whether any nodes of that type can
        # be reached (transitively, or through performing one or more attacks).
        # Consequently, it must incorporate a weight that is computed once all required
        # commands have been consilidated. Dependencies need to be determined first in
        # order to avoid erroneous exclusion when we perfrom deduplication later.

        if "Depends" in attack:

            VARs["option_type"] = attack["Depends"]

            CYPHER += (
                "MATCH path=(source)-"
                "[:TRANSITIVE|ATTACK|CREATE*0..{depth}]->(option:`{option_type}`) "
                "WHERE NOT source IN admin AND NOT option IN NODES(path)[1..-1] "
                "AND (source:Resource OR source:External) AND (option:Resource OR option:Generic) "

                "WITH DISTINCT source, option, admin, "
                "FILTER(_ IN RELS(path) WHERE STARTNODE(_):Pattern) AS dependencies "

                "WITH admin, COLLECT([source, option, REDUCE("
                "commands=[], _ IN dependencies|"
                "CASE WHEN _ IN commands THEN commands "
                "ELSE commands + _.Commands END)]"
                ") AS results "

                "UNWIND results AS result "

                "WITH admin, results, result[0] AS source, result[1] AS option, "
                "MIN(SIZE(result[2])) AS weight "

                "UNWIND results AS result "
                "WITH admin, result, source, option, weight, result[2] AS commands "
                "WHERE source = result[0] AND option = result[1] "
                "AND weight = SIZE(result[2]) "

                "WITH admin, source, option, commands, weight ORDER BY weight "
                "WITH admin, source, COLLECT([option, commands]) AS options, [NULL, []] AS grants "
            )

        if "Grants" in attack:

            # VARs["grants_type"] = ""

            CYPHER += (

                "OPTIONAL MATCH (grant:`{grants_type}`:Resource) "
                "OPTIONAL MATCH creation=(c)-[:TRANSITIVE|ATTACK|CREATE*..{depth}]"
                "->(generic:Generic:`{grants_type}`) "
                "WHERE c = source "

                "WITH DISTINCT source, options, admin, "
                "grant, generic, REDUCE(commands=[], _ IN EXTRACT("
                "_ IN FILTER(_ IN RELS(creation) "
                "WHERE STARTNODE(_):Pattern)|_.Commands)|"
                "CASE WHEN _ IN commands THEN commands "
                "ELSE commands + _ END"
                ") AS commands "

                "WITH source, options, admin, "
                "COLLECT([grant, []]) + COLLECT([generic, commands]) AS grants "
                "UNWIND grants AS grant "

                "WITH DISTINCT source, options, admin, "
                "grant[0] AS grant, grant[1] AS commands "
                "WHERE grant[0] IS NOT NULL "

                "WITH source, options, admin, "
                "COLLECT([grant, commands]) AS grants "
            )

        # Assert: WITH options, admin

        if VARs["size"] == 1 and "Depends" not in attack and "Cypher" not in attack:

            # If only one relationship is required, and there are no dependencies,
            # only direct relationships need to be identified, weight computation
            # and pruning requirements can be safely ommitted.

            VARs["requires"] = VARs["requires"][0]

            CYPHER += ' '.join((
                "MATCH path=(source)-[edge:ACTION{{Name:'{requires}', Effect: 'Allow'}}]"
                "->(target:`{target_type}`) ",

                "WHERE NOT source:Pattern ",
                "AND ALL(_ IN REVERSE(TAIL(REVERSE(NODES(path)))) WHERE NOT _ IN admin) ",
                "AND edge.Condition = '[]' " if ignore_actions_with_conditions else "",

                "%s" % process_cypher() if "Cypher" in attack else "",

                "WITH source, target, [] AS commands, options, grants ",
            ))
        else:

            # Otherwise, the attack may incorporate indirect relationships (a dependency or
            # or a combination of one or more relationships.

            CYPHER += ' '.join((

                "MATCH path=(source)-"
                "[:TRANSITIVE|ATTACK*0..{depth}]->()"
                "-[edge:ACTION]->(target:`{target_type}`)",

                "WHERE NOT source:Pattern",
                "AND ALL(_ IN REVERSE(TAIL(REVERSE(NODES(path)))) WHERE NOT _ IN admin)",
                "AND edge.Name IN {requires} AND edge.Effect = 'Allow' ",
                "AND edge.Condition = '[]' " if ignore_actions_with_conditions else "",

                "%s" % process_cypher() if "Cypher" in attack else "",

                "WITH COLLECT([source, edge.Name, target, path, options, grants]) AS results",

                "UNWIND results AS result",
                "WITH results, result[0] AS source,",
                "result[1] AS edge, result[2] AS target",

                # Eliminate all source nodes that incorporate other source nodes
                # producing the same edge to the same target. Nodes are validated
                # by counting the number of distinct edges produced.

                "WITH results, source,",
                "SIZE(COLLECT(DISTINCT edge)) AS size, target",
                "WHERE size = {size}",

                "WITH results, target, ",
                "COLLECT(DISTINCT source) AS sources ",
                "WITH results, ",
                "COLLECT(DISTINCT [target, sources]) AS pairs ",

                "UNWIND pairs AS pair ",
                "UNWIND results AS result ",

                "WITH results, ",
                "result[0] AS source, result[2] AS target, ",
                "pair[0] AS t, pair[1] AS s, ",
                "TAIL(REVERSE(TAIL(NODES(result[3])))) AS intermediaries ",
                "WHERE ALL(_ IN intermediaries WHERE NOT _ IN s) ",
                "AND target = t ",

                "WITH source, target, results ",
                "UNWIND results AS result "
                "WITH source, target, result "
                "WHERE result[0] = source "
                "AND result[2] = target "

                "WITH result[0] AS source, result[2] AS target, ",
                "result[3] AS path, result[4] AS options, ",
                "result[5] AS grants ",

                # Attack path weight: Each outcome is representative of a distinct
                # requirement that must be satisfied for the associated path to be traversed.
                # Each path may be contingent on zero or more dependencies, represented by
                # patterns that must first be executed. This set may be empty, in which case
                # the associated weight - or the number of steps required - will be zero.

                "WITH source, target, options, grants,",
                "FILTER(_ IN RELS(path) WHERE STARTNODE(_):Pattern) AS dependencies,",
                "LAST(EXTRACT(_ IN RELS(path)|_.Name)) AS outcome",

                # [source, target, options, outcome, commands, grants]

                "WITH COLLECT([source, target, options, outcome,",
                "REDUCE(commands=[], _ IN dependencies|",
                "CASE WHEN _ IN commands THEN commands ",
                "ELSE commands + _.Commands END), grants]",
                ") AS results",

                # Attack the combined minimum weight associated with each distinct source,
                # target node pair - all other results are discarded.
                # Note: this method may double count commands.

                "UNWIND results AS result",
                "WITH results, result[0] AS source, result[1] AS target,",
                "result[3] AS outcome, MIN(SIZE(result[4])) AS weight",

                "UNWIND results AS result",
                "WITH result, source, target, outcome, weight",
                "WHERE source = result[0] AND target = result[1]",
                "AND outcome = result[3] AND weight = SIZE(result[4])",

                "WITH source, target,",
                "REDUCE(commands=[], _ IN COLLECT(result[4])|",
                "CASE WHEN _ IN commands THEN commands",
                "ELSE _ + commands END) AS commands,",
                "result[2] AS options, result[5] AS grants ",
            ))

        # Assert: CYPHER includes source, targets, options, grants; where options, targets
        #         and grants comprise of (destination, commands) tuples.

        # Reduce result set to Generics only when a CreateAction has been specified.

        if OPTs["CreateAction"]:

            # Targets can only comprise of Generic nodes

            VARs["target_type"] += "`:`Generic"

        else:

            # A target must be either Generic or a Resource. If the target is Generic,
            # the source must be able to create it. This additional set of actions must
            # be reflected so that it can be incorporated into computed weights

            CYPHER += ' '.join((

                "OPTIONAL MATCH (source)-[:TRANSITIVE|ATTACK*0..{depth}]->()"
                "-->(:Pattern)-[edge:CREATE]->(target:Generic)",

                # Previous patterns may have already satisfied Dependency requirements. In order
                # to avoid duplicate steps, weights must be recomputed.

                "WITH source, target, options, grants,",
                "REDUCE(commands=[], _ IN commands + COALESCE(edge.Commands,[])|",
                "CASE WHEN _ IN commands THEN commands ",
                "ELSE commands + _ END",
                ") AS commands",

                "WHERE (NOT edge IS NULL AND target:Generic) OR target:Resource "

            ))

        # Create (source)-[:ATTACK]->(pattern:Pattern)

        CYPHER += ' '.join((

            "WITH DISTINCT source, target, options, grants,",
            "COALESCE(commands, []) AS commands",

            # Prune targets where a transitive relationship does not exist
            # when a dependency that applies to the affected node type has
            # has been specified.

            "UNWIND options AS option "
            "WITH source, target, grants, "
            "option[0] AS option,"
            "REDUCE(commands=[], _ IN commands + option[1]|"
            "CASE WHEN _ IN commands THEN commands "
            "ELSE commands + _ END"
            ") AS commands "

            "WITH source, target, commands, grants, [[NULL, []]] AS options "
            "WHERE target = option "

            if "Depends" in attack \
            and attack["Depends"] == attack["Affects"]
            else "ORDER BY SIZE(commands)",

            "WITH source, target, commands, options, grants",
            "ORDER BY SIZE(commands)",

            "WITH DISTINCT source, options, COLLECT([target, commands]) AS grants " \
            if "Grants" not in attack else \
            "WITH DISTINCT source, COLLECT([target, commands]) AS options, grants ",

            "MERGE (source)-[:ATTACK{{Name:'{attack}'}}]-> "
            "(pattern:Pattern:{attack}{{Name:'{attack}'}})",
            "ON CREATE SET ",
            "pattern.Requires = {requires_list},",
            "pattern.Depends = \"{dependency}\"",

            "WITH DISTINCT pattern, options, grants",
            "UNWIND grants AS grant",

            "WITH pattern, options,",
            "grant[0] AS grant, options[0][0] AS option,",
            "REDUCE(commands=[], _ IN options[0][1] + grant[1]|",
            "CASE WHEN _ IN commands THEN commands",
            "ELSE commands + _ END",
            ") AS history",

            "WITH pattern, options, grant, option, ",
            "%s" % cypher_resolve_commands(True),

            "MERGE (pattern)-[edge:%s{{Name:'{grants}'}}]->(grant)" \
            % ("CREATE" if OPTs["CreateAction"] \
               #   else "ADMIN" if OPTs["Admin"] \
               else "ATTACK"),
            "ON CREATE SET ",
            # "edge.Name = \"{name}\","
            "edge.Description = \"{description}\",",
            "edge.Commands = commands,",
            "edge.Weight = SIZE(commands),",
            "edge.Option = ID(option)",
            ", edge.Admin = True " if OPTs["Admin"] else "",

            # Create pattern options

            "WITH pattern, options "
            "UNWIND options AS option "
            "WITH pattern, option[0] AS option, option[1] AS commands "
            "MERGE (pattern)-[edge:OPTION{{Name:'Option'}}]->(option) "
            "ON CREATE SET "
            "edge.Weight = SIZE(commands), "
            "edge.Commands = commands " \
            if ("Depends" in attack and attack["Depends"] != attack["Affects"]) \
            or "Grants" in attack \
            else ""
        ))

        CYPHER = CYPHER.format(**VARs)

        return CYPHER

    @staticmethod
    def compute(
        max_iterations=5,
        except_attacks=[],
        only_attacks=[],
        max_search_depth="",
        ignore_actions_with_conditions=True
    ):

        exception = None

        print("[!] Removing all existing attack patterns")

        Neo4j().run("MATCH (pattern:Pattern) "
                    "OPTIONAL MATCH ()-[admin]->(:Admin) "
                    "DETACH DELETE pattern, admin")

        print("[!] Creating pseudo admin")
        Neo4j().run(Attacks._admin_cypher())

        # Temporarily set generic policy to admin. This is
        # because all attack paths that allow for reaching
        # this node implicitly grant admin.

        Neo4j().run("MATCH (policy:Generic:Policy) SET policy:Admin")

        # Identify any new attack paths, we stop when we've
        # converged or when we've exceeded the maximum number
        # of iterations.

        attack_definitions = {k: v for k, v in Attacks.definitions.items()
                              if k not in except_attacks
                              and (only_attacks == [] or k in only_attacks)}

        try:
            discovered = 0
            _ = 0
            for _ in range(1, max_iterations + 1):

                attack = 0
                created = 0

                for name, definition in attack_definitions.items():

                    exception = name
                    attack += 1

                    print("[!] Searching for attack "
                          f"{attack}/{len(attack_definitions)}: "
                          f"{name} (iteration: {_} of max: {max_iterations})")

                    cypher = Attacks._pattern_cypher(
                        name,
                        definition,
                        max_search_depth=max_search_depth,
                        ignore_actions_with_conditions=ignore_actions_with_conditions
                    )

                    summary = Neo4j().run(cypher).summary()

                    execution_time = (summary.result_available_after +
                                      summary.result_consumed_after) / 1000
                    discovered += summary.counters.nodes_created

                    if ((summary.counters.nodes_created + summary.counters.relationships_created) > 0):

                        print(f" \-> Discovered {summary.counters.nodes_created} new attack(s)",
                              f"(took: {execution_time} s).")
                        created += summary.counters.nodes_created + \
                            summary.counters.relationships_created

                # If edges are created but not nodes this loop will not break

                if created == 0:
                    break

            print("[+] Converged after" if _ <= max_iterations
                  else "[!] Failed to converge within max:",
                  f"{_} iterations. {discovered} patterns were discovered.")

            exception = None

        except Exception as e:
            print(f"[-] Neo4j returned:\n\n{e}")
            print("[!] Don't worry, we'll use what we already have")

        print("[+] Unifying attack pattern representations")

        # Remove :Admin (restore generic policy definition)
        Neo4j().run(
            "MATCH (source:Pattern)-[edge]->(policy:`AWS::Iam::Policy`:Generic:Admin) " +
            "MERGE (source)-[admin:ADMIN]->(policy) " +
            "ON CREATE SET admin = edge " +
            "DELETE edge " +
            "REMOVE policy:Admin"
        )

        # Patch generalised CYPHER queries to reflect a unified admin definition
        # Note to self: I'm not sure why we've chosen to flatten
        # (source)-->(pattern)-->(admin)

        Neo4j().run(
            "MATCH (admin:Admin), " +
            "path=(source:Resource)-[:ATTACK]->(pattern:Pattern)-[edge:ATTACK{Admin:True}]->(target) " +
            "MERGE (pattern)-[_:ATTACK]->(admin) " +
            "ON CREATE SET _ = edge, _.TargetId = ID(edge)"
        )

        # Replace all attack 'Description' entries with a 'Descriptions' set, that maps
        # to all 'Commands' present in the attack.

        # TODO: Need to work out whether a description is referencing the same edge for collection
        Neo4j().run(
            "MATCH ()-[attack:ATTACK]->() " +
            "WITH attack UNWIND attack.Commands AS command " +
            "OPTIONAL MATCH (:Pattern)-[_]->() " +
            "WHERE command IN _.Commands " +
            "WITH attack, command, _ ORDER BY _.Weight " +
            "WITH attack, command, COLLECT(_)[0] AS _ " +
            "WITH attack, COALESCE(_.Description, attack.Description) AS description " +
            "WITH attack, COLLECT(description) AS descriptions " +
            "SET attack.Descriptions = descriptions " +
            "REMOVE attack.Description"
        )

        if exception is not None:
            raise Exception(exception)
