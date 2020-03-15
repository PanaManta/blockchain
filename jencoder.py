from json import JSONEncoder

class Encoder(JSONEncoder):
    def default(self, obj):                 # pylint: disable=E0202
        if hasattr(obj,'toJSON'):
            return obj.toJSON()
        else:
            return JSONEncoder.default(self, obj)
