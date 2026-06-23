"""LinkedIn API v2 client."""

import logging

import httpx

logger = logging.getLogger("launchkit.linkedin")

LINKEDIN_API = "https://api.linkedin.com/v2"


class LinkedInService:
    """Post updates via LinkedIn API v2."""

    async def post_update(self, content: str, access_token: str) -> str | dict:
        """
        Post to LinkedIn. Returns post URN on success.
        On 403, returns manual_required dict with copy for clipboard flow.
        """
        if not access_token:
            return {"status": "manual_required", "copy": content}

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                profile_resp = await client.get(f"{LINKEDIN_API}/userinfo", headers=headers)
                if profile_resp.status_code == 403:
                    logger.warning("LinkedIn API 403 — manual post required")
                    return {"status": "manual_required", "copy": content}

                profile_resp.raise_for_status()
                profile = profile_resp.json()
                author_urn = f"urn:li:person:{profile.get('sub', '')}"

                payload = {
                    "author": author_urn,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": content},
                            "shareMediaCategory": "NONE",
                        }
                    },
                    "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
                }

                post_resp = await client.post(
                    f"{LINKEDIN_API}/ugcPosts",
                    headers=headers,
                    json=payload,
                )

                if post_resp.status_code == 403:
                    return {"status": "manual_required", "copy": content}

                post_resp.raise_for_status()
                post_id = post_resp.headers.get("x-restli-id", post_resp.json().get("id", ""))
                return post_id

        except httpx.HTTPError as exc:
            logger.error("LinkedIn post failed: %s", exc)
            return {"status": "manual_required", "copy": content, "error": str(exc)}


def get_linkedin_service() -> LinkedInService:
    return LinkedInService()
