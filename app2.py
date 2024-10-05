import sys
import os
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal, QUrl
from PyQt5.QtWebChannel import QWebChannel

class MathApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Math Application")
        self.equation_result_list = []
        self.initUI()
        self.load_data()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout()
        central_widget.setLayout(self.layout)

        # Create a web view to display MathQuill editor and equations/results
        self.web_view = QWebEngineView()
        self.layout.addWidget(self.web_view)

        # Set up the web channel for communication between JavaScript and Python
        self.web_channel = QWebChannel()
        self.handler = WebHandler(self)
        self.web_channel.registerObject('handler', self.handler)
        self.web_view.page().setWebChannel(self.web_channel)

        # Load the HTML content
        self.web_view.setHtml(self.get_html())

    def get_html(self):
        # Embed MathQuill CSS and JS directly into the HTML
        try:
            with open(r'E:\Projects\Visual Studio\Math-App\node_modules\mathquill\build\mathquill.css', 'r') as css_file:
                mathquill_css = css_file.read()
            with open(r'E:\Projects\Visual Studio\Math-App\node_modules\mathquill\build\mathquill.js', 'r') as js_file:
                mathquill_js = js_file.read()
        except Exception as e:
            mathquill_css = "/* Failed to load mathquill.css */"
            mathquill_js = "// Failed to load mathquill.js"

        # HTML content with embedded MathQuill editor and equations/results
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Math Application</title>
            <!-- Embedded MathQuill CSS -->
            <style>
            {mathquill_css}
            body {{ font-family: sans-serif; padding: 20px; }}
            #math-field {{ border: 1px solid #ccc; padding: 5px; min-height: 30px; }}
            #compute-button {{
                margin-top: 10px;
                padding: 5px 10px;
                font-size: 16px;
            }}
            #equation-list {{ margin-top: 20px; }}
            #equation-list div {{ margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <h1>Math Application</h1>
            <div id="math-field"></div>
            <button id="compute-button" onclick="sendEquation()">Compute</button>
            <div id="equation-list"></div>
            <!-- Embedded MathQuill JS -->
            <script>
            {mathquill_js}
            </script>
            <!-- Include Qt WebChannel JavaScript -->
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>
                var MQ = MathQuill.getInterface(2);
                var mathField = MQ.MathField(document.getElementById('math-field'), {{
                    spaceBehavesLikeTab: true,
                    handlers: {{
                        edit: function() {{
                            // Do something when edited
                        }}
                    }}
                }});

                function sendEquation() {{
                    var latex = mathField.latex();
                    handler.receiveEquation(latex);
                }}

                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    window.handler = channel.objects.handler;
                    handler.sendToJS.connect(function(message) {{
                        var data = JSON.parse(message);
                        if (data.savedData) {{
                            // Load saved equations and results
                            data.savedData.forEach(function(item) {{
                                addEquationResult(item.equation, item.result);
                            }});
                        }} else {{
                            // New result received
                            addEquationResult(data.equation, data.result);
                        }}
                    }});

                    // Request saved data on startup
                    handler.requestData();
                }});

                function addEquationResult(equation, result) {{
                    // Add the equation and result to the list
                    var list = document.getElementById('equation-list');
                    var item = document.createElement('div');
                    item.innerHTML = '<span>' + equation + '</span> = <span>' + result + '</span>';
                    list.appendChild(item);
                }}
            </script>
        </body>
        </html>
        '''
        return html_content

    def load_data(self):
        # Load saved equations and results
        if os.path.exists('data.json'):
            try:
                with open('data.json', 'r') as f:
                    self.equation_result_list = json.load(f)
            except json.JSONDecodeError:
                self.equation_result_list = []
        else:
            self.equation_result_list = []

    def save_data(self):
        # Save equations and results
        try:
            with open('data.json', 'w') as f:
                json.dump(self.equation_result_list, f)
        except Exception as e:
            print(f"Error saving data: {e}")

    def closeEvent(self, event):
        self.save_data()
        super().closeEvent(event)

class WebHandler(QObject):
    sendToJS = pyqtSignal(str, arguments=['message'])

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot(str)
    def receiveEquation(self, equation):
        # Compute the result using sympy
        from sympy import sympify
        try:
            expr = sympify(equation)
            result = expr.evalf()
            result_str = str(result)
        except Exception as e:
            result_str = "Error: " + str(e)

        # Add equation and result to the main window's list
        self.parent().equation_result_list.append({'equation': equation, 'result': result_str})
        # Send result back to JavaScript
        self.sendToJS.emit(json.dumps({'equation': equation, 'result': result_str}))

    @pyqtSlot()
    def requestData(self):
        # Send saved data to JavaScript
        data = self.parent().equation_result_list
        self.sendToJS.emit(json.dumps({'savedData': data}))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MathApp()
    window.show()
    sys.exit(app.exec_())
