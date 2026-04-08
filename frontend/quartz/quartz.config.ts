/**
 * CULTR Ventures — Quartz Knowledge Base Configuration
 * Serves the public-facing knowledge base at knowledge.cultrventures.com
 * Themed with Garnet Monochrome (#B91C1C)
 */

import { QuartzConfig } from "@jackyzha0/quartz/cfg"
import * as Plugin from "@jackyzha0/quartz/plugins"

const config: QuartzConfig = {
  configuration: {
    pageTitle: "CULTR Knowledge Base",
    enableSPA: true,
    enablePopovers: true,
    analytics: null,
    locale: "en-US",
    baseUrl: "knowledge.cultrventures.com",
    ignorePatterns: [
      "private",
      "templates",
      "system",
      ".obsidian",
    ],
    defaultDateType: "modified",
    theme: {
      fontOrigin: "googleFonts",
      cdnCaching: true,
      typography: {
        header: "Inter",
        body: "Inter",
        code: "JetBrains Mono",
      },
      colors: {
        lightMode: {
          light: "#fafafa",
          lightgray: "#e5e5e5",
          gray: "#a3a3a3",
          darkgray: "#404040",
          dark: "#171717",
          secondary: "#B91C1C",     // Garnet primary
          tertiary: "#DC2626",      // Garnet light
          highlight: "rgba(185, 28, 28, 0.1)",
          textHighlight: "#FEF2F2",
        },
        darkMode: {
          light: "#0a0a0a",
          lightgray: "#262626",
          gray: "#737373",
          darkgray: "#d4d4d4",
          dark: "#fafafa",
          secondary: "#DC2626",     // Garnet light
          tertiary: "#EF4444",      // Garnet lighter
          highlight: "rgba(220, 38, 38, 0.15)",
          textHighlight: "#450A0A",
        },
      },
    },
  },
  plugins: {
    transformers: [
      Plugin.FrontMatter(),
      Plugin.CreatedModifiedDate({
        priority: ["frontmatter", "filesystem"],
      }),
      Plugin.SyntaxHighlighting({
        theme: {
          light: "github-light",
          dark: "github-dark",
        },
      }),
      Plugin.ObsidianFlavoredMarkdown({ enableInHtmlBlock: false }),
      Plugin.GitHubFlavoredMarkdown(),
      Plugin.TableOfContents(),
      Plugin.CrawlLinks({ markdownLinkResolution: "shortest" }),
      Plugin.Description(),
      Plugin.Latex({ renderEngine: "katex" }),
    ],
    filters: [Plugin.RemoveDrafts()],
    emitters: [
      Plugin.AliasRedirects(),
      Plugin.ComponentResources(),
      Plugin.ContentPage(),
      Plugin.FolderPage(),
      Plugin.TagPage(),
      Plugin.ContentIndex({
        enableSiteMap: true,
        enableRSS: true,
      }),
      Plugin.Assets(),
      Plugin.Static(),
      Plugin.NotFoundPage(),
    ],
  },
}

export default config
