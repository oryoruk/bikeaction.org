# apps.bikeaction.org

This Django codebase is what powers [apps.bikeaction.org](https://apps.bikeaction.org)

Aside from the Django web site, it also hosts our [discord bot](/pba_discord/bot.py)
which is built with [interactions.py](https://interactions-py.github.io/interactions.py/).


## Getting Started

First you'll want to ensure that you have created a
[fork](https://github.com/PhillyBikeAction/abp/fork)
of this repo in your own GitHub account.
This will allow you to push your changes to GitHub so that they can be shared with the main
repository via Pull Request.

### Dependencies

The local development environment is built with
[Docker/Docker Compose](https://www.docker.com/products/docker-desktop/)
and orchestrated with [make](https://www.gnu.org/software/make/).

### Cloning the repo

Clone you fork of the repo:

```shell
git clone https://github.com/<your github username>/abp.git
```

### Starting the services

```shell
make serve
```

This command should do everything necessary to get the service up and running locally.
After it completes, you can open a browser to [http://localhost:8000/](http://localhost:8000)
to view the running web app.

You can login as `admin@example.com` with password `password`.
This user has full permissions across all parts of the app.

### Suspending the services

If you want to stop the app to save resources locally

```shell
make stop
```

Will shut down the containers.

For a more complete "get rid of it all!" or to reset a broken environment:

```
make clean
```

Will completely destroy your local containers.

## Deployment

Deployments to [apps.bikeaction.org](https://apps.bikeaction.org) occur on merge to `main` branch.

You can watch the progress of the deploy to our [dokku](https://dokku.com) instance
in the GitHub Actions output.
