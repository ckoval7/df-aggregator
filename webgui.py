from bottle import route, run, request, get, post, redirect, template, static_file

ipaddr = "127.0.0.1"

with open('accesstoken.txt', "r") as tokenfile:
    access_token = tokenfile.read().replace('\n', '')

@route('/static/<filepath:path>', name='static')
def server_static(filepath):
    return static_file(filepath, root='./static')

@get('/')
@get('/index')
def hello():
    return template('index.tpl')

@get('/cesium')
def cesium():
    return template('cesium.tpl',
    {'access_token':access_token})

def start_server():
    run(host=ipaddr, port=8080, quiet=True, debug=False, server='paste')

if __name__ == '__main__':
    start_server()
