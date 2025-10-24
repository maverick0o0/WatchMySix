#!/usr/bin/env node
const fs = require('fs/promises');
const path = require('path');

async function copyRecursive(src, dest) {
  const stats = await fs.stat(src);
  if (stats.isDirectory()) {
    await fs.mkdir(dest, { recursive: true });
    const entries = await fs.readdir(src);
    for (const entry of entries) {
      await copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
  } else {
    await fs.copyFile(src, dest);
  }
}

async function build() {
  const projectRoot = path.join(__dirname, '..');
  const srcDir = path.join(projectRoot, 'src');
  const distDir = path.join(projectRoot, 'dist');

  await fs.rm(distDir, { recursive: true, force: true });
  await fs.mkdir(distDir, { recursive: true });
  await copyRecursive(srcDir, distDir);
  console.log(`Built static assets from ${srcDir} to ${distDir}`);
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});
