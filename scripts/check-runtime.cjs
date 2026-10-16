const major = Number(process.versions.node.split('.')[0])

if (!Number.isInteger(major) || major < 22 || major >= 23) {
  console.error(`Unsupported Node.js ${process.versions.node}. Use Node 22 (recommended: 22.21.1).`)
  process.exit(1)
}

console.log(`Runtime OK: Node ${process.versions.node}`)
