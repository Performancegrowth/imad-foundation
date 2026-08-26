// Reusable SEO / AEO head manager built on react-helmet-async.
import { Helmet } from 'react-helmet-async'

const DEFAULT_IMAGE = 'https://imad.ai/logo.png'

/**
 * Renders <title>, meta description, canonical, Open Graph, Twitter card and
 * optional JSON-LD structured data (single object or array) into <head>.
 */
export default function Seo({
  title,
  description,
  canonical,
  ogTitle,
  ogDescription,
  ogImage,
  type = 'website',
  lang = 'en',
  schema,
}) {
  const oTitle = ogTitle || title
  const oDesc = ogDescription || description
  const image = ogImage || DEFAULT_IMAGE
  const schemas = Array.isArray(schema) ? schema : schema ? [schema] : []

  return (
    <Helmet>
      <html lang={lang} />
      <title>{title}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={canonical} />
      <meta property="og:title" content={oTitle} />
      <meta property="og:description" content={oDesc} />
      <meta property="og:image" content={image} />
      <meta property="og:url" content={canonical} />
      <meta property="og:type" content={type} />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={oTitle} />
      <meta name="twitter:description" content={oDesc} />
      <meta name="twitter:image" content={image} />
      {schemas.map((s, i) => (
        <script key={i} type="application/ld+json">
          {JSON.stringify(s)}
        </script>
      ))}
    </Helmet>
  )
}