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
