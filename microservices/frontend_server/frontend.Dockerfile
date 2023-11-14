# Use an Ubuntu base image
FROM ubuntu:latest

# Set the working directory to /home
WORKDIR /home/microservices/frontend_server

# Install Python and other dependencies
RUN apt-get update && \
    apt-get install -y python3 python3-pip

# Copy the current directory contents into the container at /home
COPY /microservices/frontend_server/frontend.py .

# Install Flask and requests
RUN pip3 install flask requests

# Install nano
RUN apt-get install nano -y

# Expose the port
EXPOSE 5002

# Run order.py when the container launches
CMD ["python3", "frontend.py"]
