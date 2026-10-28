# Quietline: сообщения программ в терминале остаются английскими, форматы дат и чисел
# следуют LANG сеанса. Кладётся в ~/.config/fish/conf.d/.
set -e LANGUAGE
set -gx LC_MESSAGES en_US.UTF-8
