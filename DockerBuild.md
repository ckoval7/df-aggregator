# Docker Image
A `Dockerfile` is included in this project for running the app inside a docker container. There is also a `docker-compose.yml` to simplify spinning up df-aggregator in a container with networking pre-configured to work from your host machine's browser at `http://192.168.1.1:8080`.

This can be altered/adjusted for your needs. Currently, this is provided as an optional deployment method and makes this tool more accessible to Windows users.

This containerization is a work-in-progress.

## Building the Docker Image
1. With Docker installed for your OS, simply run the following from the project root folder.
    ```console
    $ docker build --tag df-aggregator .
    ```
2. To run the container, execute the following:
    ```console
    $ docker run --name df-aggregator df-aggregator
    ```
3. Open your browser to `http://{container_ip}:8080`


## Building with Docker Compose
_You can install docker compose via pip._
1. With docker compose installed, simply run the following from the project root folder.
   ```console
   $ docker-compose up
   ```
2. Open your browser to http://127.0.0.1:8080



## Resources
For more information on Docker, see https://docs.docker.com/engine/reference/commandline/build/

For more information on Docker Compose, see https://docs.docker.com/compose/

