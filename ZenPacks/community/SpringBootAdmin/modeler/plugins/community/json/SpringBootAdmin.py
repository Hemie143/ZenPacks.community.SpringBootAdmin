# stdlib Imports
import json
import re

# Zenoss Imports
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
# Twisted Imports
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers


class SpringBootAdmin(PythonPlugin):
    """
    Doc about this plugin
    """

    requiredProperties = (
        'zSpringBootAdminPort',
        'zSpringBootAdminURI',
        'zSpringBootAdminIVGroups',
        'zSpringBootAdminIVUser',
    )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    @inlineCallbacks
    def collect(self, device, log):
        """Asynchronously collect data from device. Return a deferred/"""
        log.info('%s: collecting data', device.id)

        '''
        ip_address = device.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)
        '''

        zSpringBootAdminPort = getattr(device, 'zSpringBootAdminPort', None)
        zSpringBootAdminURI = getattr(device, 'zSpringBootAdminURI', None)
        zSpringBootAdminIVGroups = getattr(device, 'zSpringBootAdminIVGroups', None)
        zSpringBootAdminIVUser = getattr(device, 'zSpringBootAdminIVUser', None)
        if not zSpringBootAdminIVUser:
            log.error('%s: %s not set.', device.id, 'zSpringBootAdminIVUser')
            returnValue(None)

        agent = Agent(reactor)
        headers = {
                   "Accept": ['application/json'],
                   "iv-groups": [zSpringBootAdminIVGroups],
                   "iv-user": [zSpringBootAdminIVUser],
                   }

        try:
            url = 'http://{}:{}/{}'.format(device.id, zSpringBootAdminPort, zSpringBootAdminURI)
            log.debug('SBA url: {}'.format(url))
            response = yield agent.request('GET', url, Headers(headers))
            http_code = response.code
            log.debug('SBA http_code: {}'.format(http_code))
            response_body = yield readBody(response)
            log.debug('SBA response: {}'.format(response_body))
            response_body = json.loads(response_body)
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)
        returnValue([http_code, response_body])

    def process(self, device, results, log):
        log.debug('results: {}'.format(type(results)))
        # TODO: correct all gets from dicts

        http_code, applications = results
        if not (199 < http_code < 300):
            return []

        rm = []
        app_rm = []
        instance_rm = []
        component_rm = []
        # SpringBootAdmin
        om_sba = ObjectMap()
        om_sba.id = self.prepId(device.id)
        zSpringBootAdminPort = getattr(device, 'zSpringBootAdminPort', None)
        # Find build version
        for app in applications:
            if app['name'].startswith('SBA'):
                om_sba.version = app.get('buildVersion', '')
                break
        om_sba.title = '{}:{}'.format(device.id, zSpringBootAdminPort)

        log.debug('om_sba: {}'.format(om_sba))

        comp_sba = 'springBootAdmins/{}'.format(om_sba.id)

        rm.append(RelationshipMap(compname='',
                                  relname='springBootAdmins',
                                  modname='ZenPacks.community.SpringBootAdmin.SpringBootAdmin',
                                  objmaps=[om_sba]))

        # SpringBootApplication
        app_maps = []
        for application in applications:
            # application: dict
            # keys: u'buildVersion', u'status', u'instances', u'name', u'statusTimestamp'
            om_app = ObjectMap()
            app_name = application['name']
            om_app.id = self.prepId(app_name)
            app_build = application['buildVersion']
            if app_build:
                om_app.title = '{} ({})'.format(app_name, app_build)
            else:
                om_app.title = '{}'.format(app_name)
            om_app.sba_application = app_name.upper()
            app_maps.append(om_app)

            # Instances
            comp_app = '{}/springBootAdminApplications/{}'.format(comp_sba, om_app.id)
            app_instances = application['instances']
            instance_maps = []
            for instance in app_instances:
                # instance: dict
                # keys: [u'info', u'tags', u'buildVersion', u'registered', u'statusTimestamp', u'version',
                # u'statusInfo', u'registration', u'endpoints', u'id']
                om_instance = ObjectMap()
                instance_id = instance.get('id', '')
                om_instance.id = self.prepId(instance_id)
                om_instance.version = instance.get('version', '')
                instance_registration = instance.get('registration', [])
                instance_serviceUrl = instance_registration.get('serviceUrl', None)
                r = re.match(r'^(.*:)//([A-Za-z0-9\-\.]+)(:[0-9]+)?/(.*)$', instance_serviceUrl)
                if r:
                    hostingServer = r.group(2)
                    hostingPort = r.group(3)
                else:
                    hostingServer = 'UNKNOWN'
                    hostingPort = 'UNKNOWN'
                om_instance.title = '{} ({}) on {}'.format(application['name'], instance_id, hostingServer)
                om_instance.buildVersion = instance['buildVersion']
                om_instance.hostingServer = hostingServer
                om_instance.hostingPort = hostingPort
                om_instance.sba_application = app_name.upper()
                instance_maps.append(om_instance)

                # Components
                comp_instance = '{}/springBootAdminInstances/{}'.format(comp_app, om_instance.id)
                details = instance['statusInfo']['details']
                component_maps = []
                for component, data in details.items():
                    om_component = ObjectMap()
                    component_id = '{}_{}_{}'.format(app_name, instance_id, component)
                    om_component.id = self.prepId(component_id)
                    om_component.title = '{} of {} on {}'.format(component, app_name, hostingServer)
                    om_component.sba_application = app_name.upper()
                    component_maps.append(om_component)

                component_rm.append(RelationshipMap(compname=comp_instance,
                                                    relname='springBootAdminComponents',
                                                    modname='ZenPacks.community.SpringBootAdmin.SpringBootAdminComponent',
                                                    objmaps=component_maps))

            instance_rm.append(RelationshipMap(compname=comp_app,
                                               relname='springBootAdminInstances',
                                               modname='ZenPacks.community.SpringBootAdmin.SpringBootAdminInstance',
                                               objmaps=instance_maps))

        app_rm.append(RelationshipMap(compname=comp_sba,
                                      relname='springBootAdminApplications',
                                      modname='ZenPacks.community.SpringBootAdmin.SpringBootAdminApplication',
                                      objmaps=app_maps))

        rm.extend(app_rm)
        rm.extend(instance_rm)
        rm.extend(component_rm)

        # log.debug('rm: {}'.format(rm))

        return rm
