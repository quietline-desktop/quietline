# Quietline: редактор по умолчанию и приглашение starship.
set -gx EDITOR micro
set -gx VISUAL micro
if status is-interactive
    starship init fish | source
end
