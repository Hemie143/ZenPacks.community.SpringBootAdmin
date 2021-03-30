# stdlib Imports
import json
import logging

from Products.ZenUtils.Utils import prepId
# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
# Twisted Imports
from twisted.internet import reactor
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

# Setup logging
log = logging.getLogger('zen.SBAHealth')


class Health(PythonDataSourcePlugin):
    proxy_attributes = (
        'zSpringBootAdminPort',
        'zSpringBootAdminURI',
        'zSpringBootAdminIVGroups',
        'zSpringBootAdminIVUser',
    )

    status_maps = {
        'UP': 0,
        'RESTRICTED': 1,
        'Exception': 2,
        'OFFLINE': 3,
        'DOWN': 4,
    }

    status_severity_maps = {
        'UP': 0,
        'RESTRICTED': 3,
        'Exception': 3,
        'OFFLINE': 4,
        'DOWN': 5,
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.debug('In config_key {} {} {}'.format(context.device().id, datasource.getCycleTime(context),
                                                  'SBA_health'))

        return (
            context.device().id,
            datasource.getCycleTime(context),
            'SBA_health'
        )

    @classmethod
    def params(cls, datasource, context):
        log.info('Starting SBA health params')
        params = {}
        return params

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting SBA health collect')
        ds0 = config.datasources[0]
        url = 'http://{}:{}/{}'.format(config.id, ds0.zSpringBootAdminPort, ds0.zSpringBootAdminURI)
        agent = Agent(reactor)
        headers = {
                   "Accept": ['application/json'],
                   "iv-groups": [ds0.zSpringBootAdminIVGroups],
                   "iv-user": [ds0.zSpringBootAdminIVUser],
                   }
        try:
            response = yield agent.request('GET', url, Headers(headers))
            response_body = yield readBody(response)
            response_body = json.loads(response_body)
        except Exception as e:
            log.exception('{}: failed to get SBA data'.format(config.id))
            log.exception('{}: Exception: {}'.format(config.id, e))

        returnValue(response_body)

    def onSuccess(self, result, config):
        log.debug('Success - result is {}'.format(result))
        data = self.new_data()

        # SBA status
        if result:
            data['values'][config.id]['health_status'] = 0
        else:
            data['values'][config.id]['health_status'] = 5

        # TODO: Check that the component exists
        for application in result:
            app_name = application['name']
            app_id = prepId(app_name)
            app_status = application['status']
            if app_status not in self.status_maps:
                log.error('Application Status not mapped: {}'.format(app_status))
            data['values'][app_id]['health_status'] = self.status_maps.get(app_status, 3)
            # Application Instances
            app_instances = application['instances']
            for instance in app_instances:
                instance_id = prepId(instance.get('id', ''))
                instance_status = instance['statusInfo']['status']
                if instance_status not in self.status_maps:
                    log.error('Application Instance Status not mapped: {}'.format(instance_status))
                data['values'][instance_id]['health_status'] = self.status_maps.get(instance_status, 3)
                details = instance['statusInfo']['details']
                for component, c_data in details.items():
                    component_id = prepId('{}_{}_{}'.format(app_name, instance_id, component))
                    if isinstance(c_data, dict):
                        component_status = c_data['status']
                    else:
                        component_status = 'Exception'
                    if component_status not in self.status_maps:
                        log.error('Application Component Status not mapped: {}'.format(component_status))
                        log.error('Component Data: {}'.format(c_data))
                    value = self.status_maps.get(component_status, 3)
                    data['values'][component_id]['health_status'] = value

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}