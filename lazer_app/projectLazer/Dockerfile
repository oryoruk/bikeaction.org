FROM node:22-bookworm AS build

WORKDIR /code/
COPY ./ /code/

RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm install

RUN npx ionic build --prod


FROM nginx:mainline-bookworm

COPY --from=build /code/www/ /usr/share/nginx/html/
