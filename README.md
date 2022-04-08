# nervproj

NervProj is a "Project management" layer that can be used to manage the workflow on other sub-projects

## Available commands

### Checking out repositories

- To checkout a given project repository into a specific path:

```bash
$ nvp -p nvh git clone D:/Projects/NervHome
```

- Then we can init the project with a default git setup:

```bash
$ nvp -p nvh admin init
```

### Building libraries

- Force rebuilding a given library:

```bash
$ nvp build libs llvm --rebuild
```

- Building multiple libraries at once:

```bash
$ nvp build libs libiconv,zlib,libxml2
```

- Previewing the sources for a given library without actually building/rebuilding it:

```bash
$ nvp build libs libxml2 --preview
```

test
