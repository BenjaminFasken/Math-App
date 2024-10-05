# main.py
import sys
import os
import json
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QUrl  # Import QUrl here
from backend import Backend

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Math Application")
        self.resize(800, 600)  # Optional: Set initial window size

        # Initialize the WebEngineView
        self.web_view = QWebEngineView()

        # Construct the absolute path to the HTML file
        html_path = os.path.abspath("mathquill.html")
        local_url = QUrl.fromLocalFile(html_path)
        self.web_view.load(local_url)

        self.setCentralWidget(self.web_view)

        # Set up the backend and web channel for communication
        self.backend = Backend()
        self.channel = QWebChannel()
        self.channel.registerObject('backend', self.backend)
        self.web_view.page().setWebChannel(self.channel)

        # Connect the result signal to update the UI
        self.backend.resultReady.connect(self.displayResult)

        # Load saved data if available
        self.loadData()

    def displayResult(self, result_latex):
        # Escape quotes in the result to prevent JS errors
        safe_result = result_latex.replace('"', '\\"').replace('\n', '\\n')
        # Update the result div in the HTML
        script = f'document.getElementById("result").innerHTML = "{safe_result}";'
        self.web_view.page().runJavaScript(script)

    def closeEvent(self, event):
        # Save equations and results before closing
        data = {
            'equations': self.getEquations(),
            'results': self.getResults()
        }
        with open('data.json', 'w') as f:
            json.dump(data, f)
        event.accept()

    def getEquations(self):
        # Retrieve the current LaTeX input from the math field
        script = 'mathField.latex();'
        self.web_view.page().runJavaScript(script, self._handle_getEquations)
        # Since runJavaScript is asynchronous, you might need to adjust this method
        # For simplicity, we'll assume a single equation is handled
        # Implementing a proper getter requires more advanced handling
        return ""

    def _handle_getEquations(self, result):
        # Placeholder for handling the result of getEquations
        pass

    def getResults(self):
        # Similarly, retrieve the current result
        # This requires JavaScript to expose the result value
        return ""

    def setEquations(self, equations):
        # Set the equations in the math field via JavaScript
        # This assumes 'equations' is a list of LaTeX strings
        # For simplicity, handle a single equation
        if equations:
            script = f'mathField.latex("{equations[0]}");'
            self.web_view.page().runJavaScript(script)

    def setResults(self, results):
        # Set the results in the result div via JavaScript
        if results:
            result_latex = results[0].replace('"', '\\"').replace('\n', '\\n')
            script = f'document.getElementById("result").innerHTML = "{result_latex}";'
            self.web_view.page().runJavaScript(script)

    def loadData(self):
        try:
            with open('data.json', 'r') as f:
                data = json.load(f)
                self.setEquations(data.get('equations', []))
                self.setResults(data.get('results', []))
        except FileNotFoundError:
            pass  # No data to load on the first run

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
