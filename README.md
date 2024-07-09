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

- To checkout an arbitrary repository given by path into a specific path :

```bash
$ nvp git clone -u git@github.com:roche-emmanuel/sift.git D:/Projects/sift
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

### Sending rocketchat messages:

- Example of sending a rocketchat message to a given server:

```bash
$ nvp rchat "Hello from nvp command"
```

- Required rocketchat configuration elements (in the global nervproj config file, inside the **rocketchat** entry):
  - **base_url**: URL of the server, for instance **"http://192.168.0.20:3000"**
  - **default_channel**: Default channel where the message should go, for instance **"global-admin"**
  - **user_id**: User Id from the rocketchat personnal access token generated for from an existing account (should have 2FA disabled)
  - **token**: Token from the rocketchat personnal access token generated for from an existing account (should have 2FA disabled)

### Sending emails:

- Example of sending an email with a configured SMTP server:

```bash
$ nvp email "This is the email body, can use <b>html code</b>" -t "This is the email title"
```

- Required configuration elements are specified in the **email** config entry:

```json
  "email": {
    "smtp_server": "192.168.0.20:587",
    "default_username": "yyyy@nervtech.org",
    "default_password": "xxxxxxxxx",
    "default_to_addrs": "zzzz@gmail.com",
    "default_from_addr": "yyyy@nervtech.org"
  }
```
