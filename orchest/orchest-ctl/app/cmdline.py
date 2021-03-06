"""Options for the command line."""
import logging

import config
# Import the CONTAINER_MAPPING seperately because when Orchest is
# started in DEV mode, then the mapping is changed in-place.
from config import CONTAINER_MAPPING
from connections import docker_client
import utils


def get_available_cmds():
    cmds = ["start", "help", "stop", "status", "update"]
    return cmds


def start():
    # Make sure the installation is complete before starting Orchest.
    if not utils.is_install_complete():
        logging.info("Installation required. Starting installer.")
        utils.install_images()
        utils.install_network()
        logging.info("Installation finished. Attempting to start...")
        return start()

    if config.RUN_MODE == "dev":
        logging.info("Starting Orchest in DEV mode. This mounts host directories "
                     "to monitor for source code changes.")

        utils.dev_mount_inject(CONTAINER_MAPPING)
    else:
        logging.info("Starting Orchest...")

    # Clean up lingering, old images from previous starts.
    utils.clean_containers()

    # TODO: is the repo tag always the first tag in the Docker
    #       Engine API?
    # Determine the containers that are already running as we do not
    # want to run these again.
    running_containers = docker_client.containers.list()
    running_container_images = [
        running_container.image.tags[0]
        for running_container in running_containers
        if len(running_container.image.tags) > 0
    ]

    images_to_start = [
        image_name
        for image_name in config.ON_START_IMAGES
        if image_name not in running_container_images
    ]

    # Run every container that is not already running. Additionally,
    # use pre-defined container specifications if the container has
    # any.
    for container_image in images_to_start:
        container_spec = CONTAINER_MAPPING.get(container_image, {})
        run_config = utils.convert_to_run_config(container_image, container_spec)

        logging.info("Starting image %s" % container_image)
        docker_client.containers.run(**run_config)

    utils.log_server_url()


def help():
    cmds = get_available_cmds()

    help_msg = {
        "start": "Starts the Orchest application",
        "help": "Shows this help menu",
        "stop": "Stops the Orchest application",
        "status": "Checks the current status of the Orchest application",
        "update": ("Update Orchest to the latest version by pulling latest "
                   "container images"),
    }

    for cmd in cmds:
        print("{0:20}\t {1}".format(cmd, help_msg[cmd]), flush=True)


def stop():
    # TODO: shutting down can be done easier by just shutting down all the
    #       containers inside the "orchest" docker network.
    # shut down containers
    running_containers = docker_client.containers.list()

    container_names = [
        CONTAINER_MAPPING[container_key]['name']
        for container_key in CONTAINER_MAPPING
    ]

    for running_container in running_containers:
        if (len(running_container.image.tags) and
                running_container.image.tags[0] in config.ALL_IMAGES):
            # don't kill orchest-ctl itself
            if running_container.image.tags[0] == "orchestsoftware/orchest-ctl:latest":
                continue

            logging.info("Killing container %s" % running_container.name)
            try:
                running_container.kill()
                running_container.remove()
            except Exception as e:
                print(e)
        elif running_container.name in container_names:
            logging.info("Killing container %s" % running_container.name)
            try:
                running_container.kill()
                running_container.remove()
            except Exception as e:
                print(e)


def status():
    running_containers = docker_client.containers.list()

    orchest_container_names = [
        CONTAINER_MAPPING[container_key]['name']
        for container_key in CONTAINER_MAPPING
    ]

    running_prints = ['']
    not_running_prints = ['']

    for container in running_containers:
        if container.name in orchest_container_names:
            running_prints.append("Container %s running." % container.name)
            orchest_container_names.remove(container.name)

    for container_name in orchest_container_names:
        not_running_prints.append("Container %s not running." % container_name)

    if len(running_prints) > 1:
        logging.info('\n'.join(running_prints))

    if len(not_running_prints) > 1:
        logging.info('\n'.join(not_running_prints))


def update():
    logging.info("Updating Orchest...")

    for image in config.ALL_IMAGES:
        try:
            logging.info("Pulling image `%s` ..." % image)
            docker_client.images.pull(image)
            logging.info("Pulled image `%s`." % image)
        except Exception as e:
            logging.error("Something went wrong while pulling image "
                          "%s error: %s" % (image, e))
