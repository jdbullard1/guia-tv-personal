# Guía de programación personal

Guía XMLTV de programación, sin listas de reproducción ni enlaces de vídeo.

- XML ligero (hasta 48 horas): https://jdbullard1.github.io/guia-tv-personal/guia.xml
- XML completo (hasta siete días, según las fuentes): https://jdbullard1.github.io/guia-tv-personal/guia-completa.xml
- Versiones comprimidas: añadir `.gz` a cada URL XML.
- Estado y cobertura: https://jdbullard1.github.io/guia-tv-personal/estado.json

Actualización programada diariamente a las 18:23 UTC. Los horarios dependen de las fuentes públicas indicadas en `mapa.json`; GitHub puede retrasar u omitir ejecuciones. El mapa inicial contiene 183 identificadores. La actualización de programación no añade canales ni repara emisiones.

El generador rechaza una cobertura inferior al 80 % (147 identificadores) o un XML ligero superior a 4.500.000 bytes antes de publicar. Si falla, se conserva el despliegue anterior, cuya programación tiene una vigencia limitada. La guía ligera omite descripciones e imágenes. El XML completo conserva metadatos de programación; no incluye elementos de reproducción.

`actualizar.py` utiliza Python estándar y solo descarga guías públicas de las fuentes declaradas. Para una prueba sin red: `python3 actualizar.py --cache CARPETA --salida CARPETA_SALIDA`. Producción: `python3 actualizar.py` genera `site/`.

La tarea genera con permisos de lectura; publica mediante Pages con `pages:write` e `id-token:write`; después registra fecha, cobertura e ID de ejecución en `ultima-publicacion.json` mediante un job separado con `contents:write` en este repositorio. Ese registro no dispara otra ejecución. Si falla el registro, la guía ya desplegada no se revierte. El historial no garantiza evitar la política de desactivación de tareas tras 60 días sin actividad.

Uso personal, sin servicios de pago habilitados. Las fuentes conservan sus propios derechos y condiciones; la accesibilidad pública no constituye una licencia universal de redistribución de sus datos.

Referencias: [programación de Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [límites de Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits), [facturación de Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Open EPG FAQ](https://www.open-epg.com/app/faq.php).
