from http.server import HTTPServer,BaseHTTPRequestHandler
class myapi:
    def __init__(self):
        self.routes={}

    def get(self,path):
        def dec(func):
            self.routes[path]=func
            return func
        return dec
    
    def path_handler(self,path):
        if path in self.routes:
            func=self.routes[path]
            result=func()
            return result
        else:
            return '404'

    
    def run(self,host='127.0.0.1',port=8000):
        print(f"Calculator API running on http://{host}:{port}")
        routes=self.routes
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                
                
                if self.path in routes:
                    result = routes[self.path]()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(str(result).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"404 Not Found")
        
        server = HTTPServer((host, port), Handler)
        server.serve_forever()


app=myapi()

@app.get('/')
def home():
    return " this is home"
@app.get('/add/')
def about():
    return "about this page"
@app.get('/time')
def get_time():
    import time
    return f"Current time: {time.ctime()}"

app.run()


