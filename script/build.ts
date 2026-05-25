import { build as esbuild } from "esbuild";
import { build as viteBuild } from "vite";
import { rm, readFile, copyFile, access } from "node:fs/promises";

// server deps to bundle to reduce openat(2) syscalls
// which helps cold start times
const allowlist = [
  "@google/generative-ai",
  "axios",
  "cors",
  "date-fns",
  "drizzle-orm",
  "drizzle-zod",
  "express",
  "express-rate-limit",
  "express-session",
  "jsonwebtoken",
  "memorystore",
  "multer",
  "nanoid",
  "nodemailer",
  "openai",
  "passport",
  "passport-local",
  "stripe",
  "uuid",
  "ws",
  "xlsx",
  "zod",
  "zod-validation-error",
];

async function buildAll() {
  await rm("dist", { recursive: true, force: true });

  console.log("building client...");
  await viteBuild();

  console.log("building server...");
  const pkg = JSON.parse(await readFile("package.json", "utf-8"));
  const allDeps = [
    ...Object.keys(pkg.dependencies || {}),
    ...Object.keys(pkg.devDependencies || {}),
  ];
  const externals = allDeps.filter((dep) => !allowlist.includes(dep));

  await esbuild({
    entryPoints: ["server/index.ts"],
    platform: "node",
    bundle: true,
    format: "cjs",
    outfile: "dist/index.cjs",
    define: {
      "process.env.NODE_ENV": '"production"',
    },
    // Inject CJS-compatible __dirname / __filename shim so that any
    // import.meta.url-based derivations in the source are overridden
    // at the top of the bundle, before any module code runs.
    define: {
      "process.env.NODE_ENV": '"production"',
      // Rewrite all import.meta.url references to __importMetaUrl
      // which is declared in the banner below and resolves correctly in CJS.
      "import.meta.url": "__importMetaUrl",
    },
    // Banner declares __importMetaUrl using native CJS __filename.
    // This runs before all bundled code, so all rewritten import.meta.url
    // references resolve to the actual file path of the bundle.
    banner: {
      js: `var __importMetaUrl=require('url').pathToFileURL(__filename).href;`,
    },
    minify: true,
    external: externals,
    logLevel: "info",
  });

  // Copy barren land data files to dist so the server can find them
  for (const fname of ["barren_parcels_flat.json", "barren_parcels.geojson"]) {
    const src = `server/${fname}`;
    const dst = `dist/${fname}`;
    try {
      await access(src);
      await copyFile(src, dst);
      console.log(`copied ${fname} → dist/`);
    } catch {
      console.warn(`[build] ${src} not found, skipping`);
    }
  }
}

async function copyDataFiles() {
  const files = [
    "barren_parcels_flat.json",
    "barren_parcels.geojson",
  ];
  for (const f of files) {
    const src = `server/${f}`;
    const dst = `dist/${f}`;
    try {
      await access(src);
      await copyFile(src, dst);
      console.log(`✅ Copied ${f} → dist/`);
    } catch {
      console.warn(`⚠️  ${src} not found, skipping`);
    }
  }
}

buildAll()
  .then(() => copyDataFiles())
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
