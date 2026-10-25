# Instagram API capabilities (verified 2026-10-22)

**Chosen flow: Instagram API with Instagram Login** (Business Login for Instagram, host `graph.instagram.com`).
Reason: you have one professional account and no need for a linked Facebook Page. The Facebook Login variant
(`graph.facebook.com`, Page-linked accounts, different scope names) is **not** mixed in anywhere.

Sources, read 2026-10-22:
- Business Login: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login
- Account insights: https://developers.facebook.com/docs/instagram-platform/api-reference/instagram-user/insights
- Media insights: https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights
- Content publishing: https://developers.facebook.com/docs/instagram-platform/content-publishing
- Postman collection: https://www.postman.com/meta/instagram/

## Supported accounts
Professional accounts only (Creator or Business). A personal account must be switched in the Instagram app
(Settings → Account type and tools → Switch to professional account). The sync endpoint returns HTTP 409 with
that instruction if it sees a personal account. Standard Access covers accounts you own and have added to the
app; while the app is in Development mode, the account must be added as an Instagram tester.

## OAuth
| step | endpoint | implemented in |
| --- | --- | --- |
| authorize | `GET https://www.instagram.com/oauth/authorize` (client_id, redirect_uri, response_type=code, scope, state) | `instagram/client.py: authorize_url` |
| code → short-lived token | `POST https://api.instagram.com/oauth/access_token` | `exchange_code` |
| short → long-lived (60 days) | `GET https://graph.instagram.com/access_token?grant_type=ig_exchange_token` | `exchange_code` |
| refresh | `GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token` (token ≥24h old, unexpired) | `refresh_token`, auto when <10 days left |

Authorization codes are single use, valid 1 hour. A token not refreshed within 60 days cannot be refreshed: reconnect.

## Scopes requested
| scope | used for |
| --- | --- |
| `instagram_business_basic` | profile, media list (required) |
| `instagram_business_manage_insights` | account + media insights |
| `instagram_business_content_publish` | approved publishing |
| `instagram_business_manage_comments` | reserved for comment sync (not yet implemented; agent reports "unavailable") |

The old scope names (`business_basic` etc.) were deprecated 27 Jan 2025 and are not used.

## Read endpoints implemented
- `GET /{ig-user-id}?fields=user_id,username,account_type,followers_count,follows_count,media_count,...`
- `GET /{ig-user-id}/media?fields=id,caption,media_type,media_product_type,permalink,timestamp` (paginated via `paging.next`)
- `GET /{ig-user-id}/insights?metric=reach,views,accounts_engaged,total_interactions,likes,comments,shares,saves,profile_links_taps&period=day&metric_type=total_value&since&until`
- `GET /{ig-user-id}/insights?metric=follows_and_unfollows&breakdown=follow_type` — **unavailable under 100 followers**
- `GET /{media-id}/insights` — Reels: `views, reach, likes, comments, shares, saved, total_interactions, ig_reels_avg_watch_time`; Feed: same without watch time

Not used: `impressions` (deprecated), `profile_views` (not in the current list), demographic metrics (need ≥100
followers/engagements; may be added later), `reels_skip_rate` (marked "in development").

## Behaviour we rely on
- Missing data comes back as an empty set, not 0. We store `NULL` and the UI shows "unavailable".
- Insights can lag up to 48 hours. Without since/until the API looks back 24 hours.
- **No history before your first sync.** The app snapshots daily from the day you connect.
- Rate-limit errors (codes 4, 17, 32, 613) and 5xx are retried with exponential backoff (max 3).

## Publishing (Reels)
1. `POST /{ig-user-id}/media` `media_type=REELS&video_url=<public https>&caption=...` → container id
2. `GET /{container-id}?fields=status_code` until `FINISHED` (also `IN_PROGRESS`, `ERROR`, `EXPIRED`, `PUBLISHED`); polled once a minute, max 5
3. `POST /{ig-user-id}/media_publish` `creation_id=<container>` → media id
- Limit: 100 API-published posts per rolling 24 h (`GET /{ig-user-id}/content_publishing_limit`).
- **Meta fetches the video from a public URL. Local files cannot be published.** Use S3 (infra/aws) or any public HTTPS host.
- After publishing, `media_type` is `VIDEO`; `media_product_type` is `REELS`.
- In this app every publish requires an approved approval request, enforced in `instagram/service.py: execute_publish`.
