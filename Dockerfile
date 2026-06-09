FROM python:3.12-slim

WORKDIR /app

# Install uv for fast package management
RUN pip install uv

# Copy uv lock and pyproject.toml
COPY uv.lock pyproject.toml ./

# Install dependencies using uv sync
RUN uv sync --frozen

# Copy the rest of the application
COPY . .

# Expose Streamlit default port
EXPOSE 8501

# Run the app
CMD ["uv", "run", "python", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
