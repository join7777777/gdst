---
layout: default
title: 首页
---

# Following the Light

随光前行 · 灵修与默想

## Posts

{% for post in site.posts %}
- **{{ post.date | date: "%b %d, %Y" }}** — [{{ post.title }}]({{ post.url | relative_url }})
{% endfor %}

---

subscribe [via RSS]({{ "/feed.xml" | relative_url }})
