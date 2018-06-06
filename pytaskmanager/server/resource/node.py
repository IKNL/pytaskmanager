# -*- coding: utf-8 -*-
"""
Resources below '/<api_base>/node'
"""

import logging
import uuid

from flask import g, request
from flask_restful import Resource, reqparse
from . import with_user_or_node, with_user
from ._schema import *

module_name = __name__.split('.')[-1]
log = logging.getLogger(module_name)


def setup(api, api_base):
    path = "/".join([api_base, module_name])
    log.info('Setting up "{}" and subdirectories'.format(path))

    api.add_resource(
        Nodes,
        api_base + '/nodes',
        endpoint='nodes'
    )
    api.add_resource(
        Node,
        path + '/<int:uid>',
        endpoint='node'
    )
    api.add_resource(
        NodeTasks,
        path + '/<int:uid>/task',
        path + '/<int:uid>/task/<int:taskresult_id>',
    )


# Schemas
node_schema = NodeSchema()
task_result_schema = TaskResultSchema()


# ------------------------------------------------------------------------------
# Resources / API's
# ------------------------------------------------------------------------------

class Nodes(Resource):
    """resource for /api/nodes"""

    @with_user
    def get(self):
        """list of nodes that are owned by the logged-in user"""
        nodes = db.Node.get(None)

        # only the nodes of the users organization are returned
        if g.user.roles != 'admin':
            nodes = [node for node in nodes if node.organization_id == g.user.organization_id]

        return node_schema.dump(nodes, many=True)

    @with_user
    def post(self):
        """"register new node"""
        parser = reqparse.RequestParser()
        parser.add_argument(
            'collaboration_id',
            type=int,
            required=True,
            help="This field cannot be left blank!"
        )
        data = parser.parse_args()

        collaboration = db.Collaboration.get(data['collaboration_id'])

        # check that the collaboration exists
        if not collaboration:
            return {"msg": "collaboration_id '{}' does not exist".format(data['collaboration_id'])}, 400  # bad request

        # new api-key which node can use to authenticate
        api_key = str(uuid.uuid1())

        # store the new node
        # TODO an admin does not have to belong to an organization?
        organization = g.user.organization
        node = db.Node(
            name="{} - {} Node".format(organization.name, collaboration.name),
            collaboration=collaboration,
            organization=organization,
            api_key=api_key
        )
        node.save()

        return node, 201  # created


class Node(Resource):
    """"resource for /api/node/<int:id>"""

    @with_user
    def get(self, uid):
        """single node info"""
        node = db.Node.get(uid)

        if not node:
            return {"msg": "node with uid={} not found".format(uid)}, 404  # not found

        if node.organization_id != g.user.organization_id and g.user.roles != 'admin':
            return {"msg": "you are not allowed to see this node"}, 403  # forbidden

        return node_schema.dump(node, many=False), 200  # success

    @with_user
    def delete(self, uid):
        """delete node account"""
        node = db.Node.get(uid)

        if not node:
            return {"msg": "node with uid={} not found".format(uid)}, 404  # not found

        if node.organization_id != g.user.organization_id and g.user.roles != 'admin':
            return {"msg": "you are not allowed to delete this node"}, 403  # forbidden

        node.delete()

    @with_user
    def put(self, uid):
        """update existing node"""
        parser = reqparse.RequestParser()
        parser.add_argument(
            'collaboration_id',
            type=int,
            required=True,
            help="This field cannot be left blank!"
        )
        data = parser.parse_args()

        node = db.Node.get(uid)

        # create new node
        if not node:
            collaboration = db.Collaboration.get(data['collaboration_id'])

            # check that the collaboration exists
            if not collaboration:
                return {"msg": "collaboration_id '{}' does not exist".format(
                    data['collaboration_id'])}, 400  # bad request

            # new api-key which node can use to authenticate
            api_key = str(uuid.uuid1())

            # store the new node
            # TODO an admin does not have to belong to an organization?
            organization = g.user.organization
            node = db.Node(
                name="{} - {} Node".format(organization.name, collaboration.name),
                collaboration=collaboration,
                organization=organization,
                api_key=api_key
            )
            node.save()
        else:  # update node
            if node.organization_id != g.user.organization_id and g.user.roles != 'admin':
                return {"msg": "you are not allowed to edit this node"}, 403  # forbidden

            node.collaboration_id = data['collaboration_id']
            node.save()

        return node


class NodeTasks(Resource):
    """Resource for /api/node/<int:id>/task.
    returns task(s) belonging to a specific node

       Resource for /api/node/<int:id>/task/<int:id>
    returns


    TODO do we need the second usage? we can retrieve tasks by the endpoint /api/task
    TODO if we do want to keep this, we need to make sure the user only sees task that belong to this node
    TODO also the user can only see nodes which belong to their organization
    """

    @with_user_or_node
    def get(self, uid, taskresult_id=None):
        """Return a list of tasks for a node or a single task <taskresult_id> belonging t.

        If the query parameter 'state' equals 'open' the list is
        filtered to return only tasks without result.
        """
        global log
        log = logging.getLogger(__name__)

        if taskresult_id is not None:
            result = db.TaskResult.get(taskresult_id)
            return task_result_schema.dump(result)

        # get tasks that belong to node <uid>
        node = db.Node.get(uid)

        # filter tasks if a specific state is requested
        if request.args.get('state') == 'open':
            results = [result for result in node.taskresults if not result.finished_at]
            return task_result_schema.dump(results, many=True)

        return [result for result in node.taskresults]