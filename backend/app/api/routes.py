import json
import inspect
import re

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from backend.app.errors import HubError, require, success
from backend.app.models import inputs as models
from backend.app.services.authorization import admin, principal
from backend.app.security.packages import digest


def create_routes(hub, identity):
    public = APIRouter()

    def check_origin(request):
        require(
            request.headers.get("origin") in hub.settings.web_origins,
            "CSRF_INVALID",
            "请求来源不匹配",
            403,
        )

    def authenticate(request: Request):
        bearer = request.headers.get("authorization", "")
        if bearer:
            require(bearer.lower().startswith("bearer "), "UNAUTHENTICATED", "需要 Bearer Token", 401)
            claims = identity.validate_access(bearer[7:])
            require("skills:read" in claims["scope"].split(), "FORBIDDEN", "缺少读取授权", 403)
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                require("skills:write" in claims["scope"].split(), "FORBIDDEN", "缺少写入授权", 403)
            user_id = claims["sub"]
            request.state.auth_channel = "bearer"
        else:
            user_id, session = identity.session(request.cookies.get("skillhub_session"))
            request.state.auth_channel = "web"
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                check_origin(request)
                identity.csrf(session, request.headers.get("x-csrf-token"))
        request.state.user_id = user_id
        return user_id

    api = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)])

    def run(request, action, arguments=None):
        channel = "web" if request.state.auth_channel == "web" else "rest"
        return success(hub.run(request.state.user_id, action, arguments, channel=channel))

    @public.post("/api/v1/auth/login")
    def login(request: Request, body: models.Login):
        check_origin(request)
        raw, csrf, user_id = identity.login(
            body.username, body.password, request.client.host if request.client else "local"
        )
        identity.logout(request.cookies.get("skillhub_session"))
        response = JSONResponse(success(hub.run(user_id, "whoami")))
        for name, value, httponly in [("skillhub_session", raw, True), ("skillhub_csrf", csrf, False)]:
            response.set_cookie(
                name,
                value,
                httponly=httponly,
                samesite="lax",
                secure=False,
                max_age=hub.settings.session_minutes * 60,
                path="/",
            )
        return response

    @api.post("/auth/logout")
    def logout(request: Request):
        identity.logout(request.cookies.get("skillhub_session"))
        response = JSONResponse(success({"logged_out": True}))
        response.delete_cookie("skillhub_session", path="/")
        response.delete_cookie("skillhub_csrf", path="/")
        return response

    @api.get("/me")
    def me(request: Request):
        return run(request, "whoami")

    @api.get("/runtime")
    def runtime(request: Request):
        return success({"mcp_endpoint": hub.settings.resource, "web_url": hub.settings.base_url + "/app"})

    @api.post("/installations/preflight")
    def preflight(request: Request, body: models.Install):
        arguments = body.model_dump()
        arguments.pop("workspace_id")
        return run(request, "get_skill_install_plan", arguments)

    @api.get("/teams")
    def teams(request: Request):
        return run(request, "list_my_teams")

    @api.get("/categories")
    def categories(request: Request):
        return run(request, "list_skill_categories")

    @api.get("/analytics")
    def analytics(request: Request, days: int = Query(30, ge=1, le=365)):
        return run(request, "usage_stats", {"days": days})

    @api.get("/skills/{skill_id}/stats")
    def skill_stats(request: Request, skill_id: str, days: int = Query(30, ge=1, le=365)):
        return run(request, "usage_stats", {"days": days, "skill_id": skill_id})

    @api.get("/skills")
    def skills(
        request: Request,
        query: str = "",
        category: str | None = None,
        team_id: str | None = None,
        cursor: str | None = None,
        limit: int = Query(30, ge=1, le=100),
        tags: list[str] | None = Query(None),
        sort: str = "recent",
    ):
        return run(
            request,
            "list_skills",
            locals_for(
                query=query,
                category=category,
                team_id=team_id,
                cursor=cursor,
                limit=limit,
                tags=tags,
                sort=sort,
            ),
        )

    @api.get("/skills/{skill_id}")
    def skill(request: Request, skill_id: str):
        return run(request, "get_skill", {"skill_id": skill_id})

    @api.get("/skills/{skill_id}/versions")
    def versions(request: Request, skill_id: str):
        return run(request, "list_skill_versions", {"skill_id": skill_id})

    @api.get("/skills/{skill_id}/versions/{version}/files/{relative_path:path}")
    def file(request: Request, skill_id: str, version: str, relative_path: str):
        return run(
            request,
            "get_skill_file",
            locals_for(skill_id=skill_id, version=version, relative_path=relative_path),
        )

    @api.get("/favorites")
    def favorites(request: Request):
        return run(request, "list_favorites")

    @api.delete("/favorites/{skill_id}")
    def unfavorite(request: Request, skill_id: str):
        return run(request, "remove_favorite", {"skill_id": skill_id})

    @api.get("/collections")
    def collections(request: Request, team_id: str | None = None):
        return run(request, "list_collections", {"team_id": team_id})

    @api.get("/collections/{collection_id}/skills")
    def collection_skills(request: Request, collection_id: str):
        return run(request, "list_collection_skills", {"collection_id": collection_id})

    @api.delete("/collections/{collection_id}/skills/{skill_id}")
    def collection_remove(request: Request, collection_id: str, skill_id: str):
        return run(
            request,
            "remove_skill_from_collection",
            locals_for(collection_id=collection_id, skill_id=skill_id),
        )

    @api.get("/my/uploads")
    def my_uploads(request: Request):
        return run(request, "list_my_uploads")

    @api.get("/reviews")
    def reviews(request: Request):
        return run(request, "list_reviews")

    @api.get("/reviews/{review_id}")
    def review(request: Request, review_id: str):
        return run(request, "get_skill_review_status", {"review_id": review_id})

    @api.get("/share-targets")
    def share_targets(request: Request):
        return run(request, "share_targets")

    @api.get("/installations")
    def installations(request: Request):
        return run(request, "list_installed_skills")

    @api.get("/installations/updates/check")
    def updates(request: Request):
        return run(request, "check_skill_updates")

    @api.get("/recommendations")
    def recommendations(
        request: Request,
        query: str = "",
        limit: int = Query(6, ge=1, le=30),
        tags: list[str] | None = Query(None),
    ):
        return run(request, "recommend_skills", locals_for(query=query, limit=limit, tags=tags))

    @api.get("/issues")
    def issues(request: Request):
        return run(request, "list_issues")

    @api.get("/admin/users")
    def users(request: Request):
        return run(request, "admin_users")

    @api.get("/admin/teams")
    def admin_teams(request: Request):
        return run(request, "admin_teams")

    @api.get("/audit-events")
    def audit(request: Request, limit: int = Query(100, ge=1, le=500)):
        with hub.repo.transaction() as tx:
            require(admin(principal(tx, request.state.user_id)))
            tx.audit(request.state.user_id, "audit_events_query")
        return success(list(reversed(hub.repo.audit_events()))[:limit])

    @api.get("/oauth/grants")
    def grants(request: Request):
        return success(identity.grants(request.state.user_id))

    @api.delete("/oauth/grants/{grant_id}")
    def revoke_grant(request: Request, grant_id: str):
        identity.revoke_grant(request.state.user_id, grant_id)
        return success({"revoked": True})

    def mutation(path, action, model, method="POST", exclude_none=False):
        def endpoint(request: Request, body: model, **_path_values):
            if action == "decide_review":
                require(
                    request.state.auth_channel == "web",
                    "WEB_APPROVAL_REQUIRED",
                    "审核决定须在 Web 会话中确认，不能使用 MCP Bearer 凭据审批",
                    403,
                )
            arguments = body.model_dump(exclude_none=exclude_none)
            arguments.update(request.path_params)
            return run(request, action, arguments)

        endpoint.__name__ = action + "_" + str(len(api.routes))
        endpoint.__signature__ = inspect.Signature(
            [
                inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request),
                inspect.Parameter("body", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=model),
                *[
                    inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=str)
                    for name in re.findall(r"\{(\w+)\}", path)
                ],
            ]
        )
        api.add_api_route(path, endpoint, methods=[method], name=action)

    mutation("/favorites", "add_favorite", models.SkillRef)
    mutation("/collections", "create_collection", models.CollectionCreate)
    mutation("/collections/{collection_id}", "edit_collection", models.CollectionEdit, "PATCH")
    mutation("/collections/{collection_id}/skills", "add_skill_to_collection", models.SkillRef)
    mutation("/skills", "upload_skill", models.Upload)
    mutation("/skills/{skill_id}/versions", "upload_skill", models.Upload)
    mutation("/skills/{skill_id}", "edit_skill", models.SkillEdit, "PATCH", True)
    mutation("/skills/{skill_id}/versions/{version}/status", "set_version_status", models.VersionStatus)
    mutation("/skills/{skill_id}/reviews", "request_skill_review", models.VersionRef)
    mutation("/skills/{skill_id}/download", "create_download", models.VersionRef)
    mutation("/reviews/{review_id}/decision", "decide_review", models.Decision)
    mutation("/skills/{skill_id}/sharing", "share_skill", models.Sharing)
    mutation("/skills/{skill_id}/sharing/revoke", "revoke_share", models.Sharing)
    mutation("/skills/{skill_id}/ratings", "rate_skill", models.Rating)
    mutation("/skills/{skill_id}/issues", "report_skill_issue", models.IssueCreate)
    mutation("/issues/{issue_id}", "update_issue", models.IssueEdit, "PATCH")
    mutation("/uploads/prepare", "prepare_skill_upload", models.PrepareUpload)
    mutation("/installations/plan", "install_skill", models.Install)
    mutation("/installations", "report_install_result", models.InstallReport)
    mutation("/installations/update", "update_skill", models.UpdateInstall)
    mutation("/installations/uninstall", "uninstall_skill", models.Uninstall)
    mutation("/admin/users", "create_user", models.UserCreate)
    mutation("/admin/users/{user_id}", "edit_user", models.UserEdit, "PATCH", True)
    mutation("/admin/users/{user_id}/password", "reset_password", models.PasswordReset)
    mutation("/admin/teams", "create_team", models.TeamCreate)
    mutation("/admin/teams/{team_id}", "edit_team", models.TeamEdit, "PATCH", True)
    mutation("/admin/teams/{team_id}/members", "set_membership", models.MemberEdit)

    @api.post("/uploads")
    async def web_upload(request: Request):
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                body = models.PrepareUpload.model_validate(await request.json())
            except (ValidationError, ValueError) as exc:
                raise HubError("UPLOAD_INVALID", "上传会话参数无效", 422) from exc
            return run(request, "prepare_skill_upload", body.model_dump())
        form = await request.form(max_files=1, max_fields=4, max_part_size=hub.settings.max_zip)
        uploaded = form.get("file")
        require(uploaded and hasattr(uploaded, "read"), "UPLOAD_INVALID", "请选择文件", 400)
        content = await uploaded.read(hub.settings.max_zip + 1)
        require(len(content) <= hub.settings.max_zip, "UPLOAD_INVALID", "文件超过 2 MiB", 413)
        try:
            metadata = json.loads(form.get("metadata", "{}"))
            if uploaded.filename == "SKILL.md":
                metadata["skill_md"] = content.decode("utf-8")
            elif uploaded.filename.lower().endswith(".zip"):
                session = hub.run(
                    request.state.user_id,
                    "prepare_skill_upload",
                    {
                        "team_id": metadata.get("team_id"),
                        "filename": uploaded.filename,
                        "size": len(content),
                        "sha256": digest(content),
                    },
                )
                ticket = session["upload_url"].rsplit("/", 1)[1]
                hub.redeem_upload(ticket, content)
                metadata["upload_id"] = session["upload_id"]
            else:
                raise HubError("UPLOAD_INVALID", "请选择 SKILL.md 或 ZIP", 400)
            body = models.Upload.model_validate(metadata)
        except (ValueError, UnicodeError, ValidationError) as exc:
            raise HubError("UPLOAD_INVALID", "上传元数据或文件无效", 422) from exc
        return run(request, "upload_skill", body.model_dump())

    @public.post("/api/v1/transfers/upload/{ticket}")
    async def transfer_upload(request: Request, ticket: str):
        require(len(ticket) <= 100, "UPLOAD_EXPIRED", "票据无效", 410)
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            require(len(content) <= hub.settings.max_zip, "UPLOAD_INVALID", "上传过大", 413)
        return success(hub.redeem_upload(ticket, bytes(content)))

    @public.get("/api/v1/transfers/download/{ticket}")
    def transfer_download(ticket: str):
        require(len(ticket) <= 100, "DOWNLOAD_EXPIRED", "票据无效", 410)
        content, filename = hub.redeem_download(ticket)
        return Response(
            content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return public, api


def locals_for(**kwargs):
    return kwargs
