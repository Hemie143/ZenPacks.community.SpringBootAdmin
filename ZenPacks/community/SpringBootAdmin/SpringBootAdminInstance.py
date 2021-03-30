from . import schema


class SpringBootAdminInstance(schema.SpringBootAdminInstance):

    status_maps ={
                  0: 'UP',
                  1: 'RESTRICTED',
                  2: 'Exception',
                  3: 'OFFLINE',
                  4: 'DOWN',
    }

    def get_status(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('health_status')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.status_maps:
            return self.status_maps.get(value)
        return 'Undefined'
