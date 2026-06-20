---
layout: default
title: 首页
---

# Following the Light

随光前行 · 灵修与默想

## Posts

<ul>
  {% for post in site.posts %}
  <li>
    <span>{{ post.date | date: "%b %d, %Y" }}</span>
    <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
    {% if post.image %}
    <img src="{{ post.image | relative_url }}" alt="{{ post.title }}" style="max-width:300px;">
    {% endif %}
  </li>
  {% endfor %}
</ul>

subscribe [via RSS]({{ "/feed.xml" | relative_url }})
