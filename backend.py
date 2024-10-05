# backend.py
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal

class Backend(QObject):
    resultReady = pyqtSignal(str)

    @pyqtSlot(str)
    def computeResult(self, latex_input):
        # Process the LaTeX input and compute the result
        from sympy import sympify, latex
        try:
            # Convert LaTeX to SymPy expression
            expr = sympify(latex_input)
            result = expr.doit()  # Compute the result
            result_latex = latex(result)
            self.resultReady.emit(result_latex)
        except Exception as e:
            self.resultReady.emit(f"Error: {e}")
