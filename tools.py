"""Simple tools for testing multi-cycle token tracking"""

from strands import tool


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression.

    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")

    Returns:
        The result of the calculation as a string
    """
    try:
        # Safe evaluation of mathematical expressions
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def temperature_converter(value: float, from_unit: str, to_unit: str) -> str:
    """
    Convert temperature between Celsius and Fahrenheit.

    Args:
        value: The temperature value to convert
        from_unit: Source unit, either "C" or "F"
        to_unit: Target unit, either "C" or "F"

    Returns:
        The converted temperature as a formatted string
    """
    from_unit = from_unit.upper()
    to_unit = to_unit.upper()

    if from_unit == to_unit:
        return f"{value}°{from_unit}"

    if from_unit == "C" and to_unit == "F":
        result = (value * 9/5) + 32
        return f"{result:.1f}°F"
    elif from_unit == "F" and to_unit == "C":
        result = (value - 32) * 5/9
        return f"{result:.1f}°C"
    else:
        return f"Error: Invalid units. Use 'C' or 'F'"
