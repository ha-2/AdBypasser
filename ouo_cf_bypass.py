import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from PyBypass.main import UnableToBypassError

ANCHOR_URL = (
    "https://www.google.com/recaptcha/api2/anchor?"
    "ar=1&k=6Lcr1ncUAAAAAH3cghg6cOTPGARa8adOf-y9zv2x&"
    "co=aHR0cHM6Ly9vdW8uaW86NDQz&hl=en&"
    "v=1B_yv3CBEV10KtI2HJ6eEXhJ&size=invisible&cb=4xnsug1vufyr"
)


def recaptcha_v3(session, anchor_url: str) -> str:
    url_base = "https://www.google.com/recaptcha/"
    post_data = "v={}&reason=q&c={}&k={}&co={}"
    matches = re.findall(r"([api2|enterprise]+)\/anchor\?(.*)", anchor_url)
    if not matches:
        raise UnableToBypassError("Unable to build reCAPTCHA request.")
    matches = matches[0]
    url_base += f"{matches[0]}/"
    params = matches[1]
    res = session.get(f"{url_base}anchor", params=params, timeout=15)
    token_matches = re.findall(r'"recaptcha-token" value="(.*?)"', res.text)
    if not token_matches:
        raise UnableToBypassError("Unable to extract reCAPTCHA token.")
    token = token_matches[0]
    params = dict(pair.split("=") for pair in params.split("&"))
    post_data = post_data.format(params["v"], token, params["k"], params["co"])
    res = session.post(
        f"{url_base}reload",
        params=f'k={params["k"]}',
        data=post_data,
        timeout=15,
    )
    answer_matches = re.findall(r'"rresp","(.*?)"', res.text)
    if not answer_matches:
        raise UnableToBypassError("Unable to resolve reCAPTCHA response.")
    answer = answer_matches[0]
    return answer


def ouo_bypass(url: str) -> str:
    try:
        import cloudscraper
    except ModuleNotFoundError as exc:
        raise UnableToBypassError(
            "cloudscraper is required to bypass ouo.io; install dependencies."
        ) from exc

    session = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    tempurl = url.replace("ouo.press", "ouo.io")
    parsed = urlparse(tempurl)
    short_id = tempurl.split("/")[-1]

    res = session.get(
        tempurl,
        headers={"user-agent": "Mozilla/5.0"},
        timeout=20,
    )
    next_url = f"{parsed.scheme}://{parsed.hostname}/go/{short_id}"

    for _ in range(2):
        if res.headers.get("Location"):
            break

        if res.status_code in {403, 503} and not res.content:
            raise UnableToBypassError("Cloudflare challenge blocked the request.")

        soup = BeautifulSoup(res.content, "html.parser")
        form = soup.form
        if not form:
            raise UnableToBypassError(
                f"Unable to find ouo form payload (status {res.status_code})."
            )
        inputs = form.find_all("input", {"name": re.compile(r"token$")})
        data = {input_tag.get("name"): input_tag.get("value") for input_tag in inputs}
        if not data:
            raise UnableToBypassError("Unable to extract ouo form tokens.")

        data["x-token"] = recaptcha_v3(session, ANCHOR_URL)
        res = session.post(
            next_url,
            data=data,
            headers={"content-type": "application/x-www-form-urlencoded"},
            allow_redirects=False,
            timeout=20,
        )
        next_url = f"{parsed.scheme}://{parsed.hostname}/xreallcygo/{short_id}"

    bypassed_link = res.headers.get("Location")
    if not bypassed_link:
        raise UnableToBypassError("Unable to resolve ouo redirect location.")
    return str(bypassed_link)
