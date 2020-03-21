create table if not exists twitch (
  id       serial primary key,
  username text   not null
);
create unique index if not exists twitch_username_idx on twitch(username);
