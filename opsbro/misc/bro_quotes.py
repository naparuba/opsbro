import random

quotes = [
    ("Dead or alive, you're coming with me.", 'RoboCop'),
    
    ("I never broke the law. I am the law!", 'Judge Dredd'),
    
    ("I will look for you, I will find you, and I will kill you.", 'Taken'),
    
    ("You've got to ask yourself one question: 'Do I feel lucky?' Well, do ya, punk?", 'Dirty Harry'),
    
    ("Yippie-ki-yay, motherf***er.", 'Die Hard'),
    
    ("Hasta la vista, baby.", 'Terminator 2: Judgement Day'),
    
    ("This is Sparta!", '300'),
    
    ("Say hello to my little friend.", 'Scarface'),
    
    ("I'll be back.", 'Terminator'),
    
    ("Get off my plane!", 'Air Force One'),
    
    ("At my signal, unleash hell.", 'Gladiator'),
    
    ("If it bleeds, we can kill it.", 'Predator'),
    
    ("Come with me if you want to live.", 'Terminator'),
    
    ("Let's put a smile on that face.", 'The Dark Knight'),
    
    (" I got all the time in the world. *You* don't, but I do.", 'Man on Fire'),
    
    ("I ain't got time to bleed.", 'Predator'),
    
    ("Forgiveness is between them and God. It's my job to arrange the meeting.", 'Man on Fire'),
    
    ("I could have killed 'em all, I could kill you. In town you're the law, out here it's me. Don't push it. Don't push it or I'll give you a war you won't believe. Let it go. Let it go.", 'Rambo'),
    
    ("I'll make him an offer he can't refuse.", 'The Godfather'),
    
    ("Remember Sully when I promised to kill you last? I lied.", 'Commando'),
    
    ("None of you understand. I'm not locked up in here with you. You're locked up in here with me.", 'Watchmen'),
    
    ("I have come here to chew bubble gum and kick ass...and I'm all out of bubble gum.", 'They Live'),
    
    ("Mongol General: What is best in life? Conan: To crush your enemies, to see them driven before you, and to hear the lamentations of their women!", 'Conan'),
    
    ("Don't let your mouth get your ass in trouble.", 'Shaft'),
    
    ("Imagine the future, Chains, 'cause you're not in it.", 'Stone Cold'),
    
    ("You're a disease... And I'm the cure.", 'Cobra'),
]


def get_quote():
    return random.sample(quotes, 1)[0]
