const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const outputDirectory = path.resolve(__dirname, '..', 'dist');
const homepagePath = path.join(outputDirectory, 'index.html');
const homepage = fs.readFileSync(homepagePath, 'utf8');

assert.match(homepage, /<html\b[^>]*\blang="es"/, 'Homepage should declare its language');
assert.match(homepage, /<title>GART Gallery/, 'Homepage should have a descriptive title');
assert.match(homepage, /<meta name="description"/, 'Homepage should have a meta description');

for (const route of ['works/index.html', 'works/1/index.html', 'galleries/index.html', 'galleries/1/index.html']) {
  assert.ok(fs.existsSync(path.join(outputDirectory, route)), `Missing generated route: ${route}`);
}

console.log('Homepage metadata and generated routes passed SEO checks.');
