<template>
  <div class="chat-markdown" v-html="html" @click="handleMarkdownClick"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import css from 'highlight.js/lib/languages/css'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdownLang from 'highlight.js/lib/languages/markdown'
import python from 'highlight.js/lib/languages/python'
import shell from 'highlight.js/lib/languages/shell'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

const props = defineProps<{
  content: string
}>()

const emit = defineEmits<{
  'citation-click': [href: string]
}>()

const MAX_RENDER_CACHE_SIZE = 360
const renderCache = new Map<string, string>()

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', shell)
hljs.registerLanguage('shell', shell)
hljs.registerLanguage('zsh', shell)
hljs.registerLanguage('css', css)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('vue', xml)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('jsonc', json)
hljs.registerLanguage('markdown', markdownLang)
hljs.registerLanguage('md', markdownLang)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('tsx', typescript)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight: (code, language) => highlightCode(code, language),
})

markdown.renderer.rules.fence = (tokens, idx, options) => {
  const token = tokens[idx]
  const language = token.info.trim().split(/\s+/)[0] || 'text'
  const highlighted = options.highlight?.(token.content, language, '') || markdown.utils.escapeHtml(token.content)
  const langLabel = markdown.utils.escapeHtml(language)
  return `<div class="studio-code-block" data-language="${langLabel}">`
    + `<div class="studio-code-header"><span>${langLabel}</span><button type="button" class="studio-code-copy" title="复制代码">复制</button></div>`
    + `<pre class="hljs studio-code-pre"><code>${highlighted}</code></pre>`
    + `</div>`
}

const html = computed(() => renderMarkdownCached(props.content || ''))

function normalizeCodeLanguage(language: string | undefined) {
  const value = String(language || '').trim().toLowerCase().replace(/^language-/, '')
  const aliases: Record<string, string> = {
    console: 'shell',
    powershell: 'shell',
    ps1: 'shell',
    plaintext: 'text',
    text: 'text',
  }
  return aliases[value] || value
}

function highlightCode(code: string, language: string | undefined) {
  const normalized = normalizeCodeLanguage(language)
  if (normalized && normalized !== 'text' && hljs.getLanguage(normalized)) {
    return hljs.highlight(code, { language: normalized, ignoreIllegals: true }).value
  }
  return markdown.utils.escapeHtml(code)
}

function renderMarkdownCached(content: string) {
  const cached = renderCache.get(content)
  if (cached !== undefined) {
    renderCache.delete(content)
    renderCache.set(content, cached)
    return cached
  }
  const rendered = markdown.render(content || '')
  renderCache.set(content, rendered)
  while (renderCache.size > MAX_RENDER_CACHE_SIZE) {
    const firstKey = renderCache.keys().next().value
    if (firstKey === undefined) break
    renderCache.delete(firstKey)
  }
  return rendered
}

async function handleMarkdownClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  const citationLink = target?.closest<HTMLAnchorElement>('a[href^="studio-citation:"]')
  if (citationLink) {
    event.preventDefault()
    emit('citation-click', citationLink.getAttribute('href') || '')
    return
  }
  const button = target?.closest<HTMLButtonElement>('.studio-code-copy')
  if (!button) return
  const block = button.closest('.studio-code-block')
  const code = block?.querySelector('code')?.textContent || ''
  if (!code) return
  try {
    await writeClipboardText(code)
    button.textContent = '已复制'
    window.setTimeout(() => {
      button.textContent = '复制'
    }, 1200)
  } catch {
    button.textContent = '复制失败'
    window.setTimeout(() => {
      button.textContent = '复制'
    }, 1200)
  }
}

async function writeClipboardText(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'readonly')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  const ok = document.execCommand('copy')
  document.body.removeChild(textarea)
  if (!ok) throw new Error('copy failed')
}
</script>
