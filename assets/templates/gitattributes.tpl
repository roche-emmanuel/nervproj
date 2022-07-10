###############################
# Git Line Endings            #
###############################

# Set default behaviour to automatically normalize line endings.
* text=auto

# Force batch scripts to always use CRLF line endings so that if a repo is accessed
# in Windows via a file share from Linux, the scripts will work.
*.{cmd,[cC][mM][dD]} text eol=crlf
*.{bat,[bB][aA][tT]} text eol=crlf

# Force bash scripts to always use LF line endings so that if a repo is accessed
# in Unix via a file share from Windows, the scripts will work.
*.sh text eol=lf

# Archives
*.7z -text
*.br -text
*.gz -text
*.tar -text
*.zip -text

# Documents
*.pdf -text

# Images
*.gif -text
*.ico -text
*.jpg -text
*.pdf -text
*.png -text
*.psd -text
*.webp -text

# Fonts
*.woff2 -text

# Other
*.exe -text
